
import json

from sqlalchemy.orm import Session

from app.models import Ticket, TicketAIResult, TicketHistory
from app.services.llm_service import (
    classify_ticket,
    generate_resolution,
)
from app.services.vector_store import search_chunks
from app.services.evidence_validator import validate_resolution
from app.config import settings


CONFIDENCE_THRESHOLD = 0.50


def _safe_fallback(result, reason):
    """
    Clear unsafe persisted AI output and prepare human review.
    This helper is only for SQLAlchemy TicketAIResult objects.
    """

    result.available = True
    result.root_cause = (
        "Unable to establish a fully verified root cause."
    )
    result.resolution_steps = "[]"
    result.customer_response = (
        "Thank you for contacting support. "
        "Some details of your issue require further verification. "
        "Our support team will review your case and assist you."
    )
    result.sources = "[]"
    result.recommended_next_action = (
        "Human support review required. "
        "Follow only the documented support procedure."
    )
    result.escalation_required = True
    result.escalation_reason = reason


def _apply_resolution_fallback(resolution, reason):
    """
    Clear unsafe generated content.
    This helper is only for Pydantic Resolution objects.
    """

    resolution.escalation_required = True
    resolution.escalation_reason = reason
    resolution.root_cause = (
        "Unable to establish a fully verified root cause."
    )
    resolution.summary = (
        "The issue requires human review because the available "
        "evidence does not support a complete resolution."
    )
    resolution.resolution_steps = []
    resolution.customer_response = (
        "Thank you for contacting support. "
        "Some details of your issue require further verification. "
        "Our support team will review your case and assist you."
    )
    resolution.sources = []


def _record_escalation(db, ticket, reason):
    """Record an escalation only when the ticket changes status."""

    if ticket.status not in ("Escalated", "Resolved"):
        db.add(
            TicketHistory(
                ticket_id=ticket.ticket_id,
                old_status=ticket.status,
                new_status="Escalated",
                note=reason or "Human review required.",
            )
        )

        ticket.status = "Escalated"


def analyze_and_resolve(db: Session, ticket: Ticket):

    # Step 1: Classify ticket.
    try:
        classification = classify_ticket(ticket)

    except Exception:
        db.rollback()
        db.refresh(ticket)

        result = ticket.ai_result or TicketAIResult(
            ticket_id=ticket.ticket_id
        )

        _safe_fallback(
            result,
            "AI classification unavailable; human review required.",
        )

        # Classification failure means AI is unavailable.
        result.available = False

        _record_escalation(
            db,
            ticket,
            result.escalation_reason,
        )

        db.add(result)
        db.commit()
        db.refresh(result)

        return result

    ticket.category = classification.category
    ticket.priority = classification.priority

    # Step 2: Retrieve relevant knowledge-base evidence.
    try:
        evidence = [
            item
            for item in search_chunks(
                ticket.subject + " " + ticket.description
            )
            if item["score"] >= settings.similarity_threshold
        ]

    except Exception:
        evidence = []

    # Step 3: Handle missing evidence without calling the LLM.
    if not evidence:
        result = ticket.ai_result or TicketAIResult(
            ticket_id=ticket.ticket_id
        )

        result.sentiment = classification.sentiment
        result.intent = classification.intent
        recommended_next_action = (
            "Human support review required. "
            "Verify the available documentation before responding."
        )
        result.main_issue = classification.main_issue
        result.summary = classification.summary
        result.confidence = 0.0

        _safe_fallback(
            result,
            "Insufficient relevant knowledge-base evidence.",
        )

        _record_escalation(
            db,
            ticket,
            result.escalation_reason,
        )

        db.add(result)
        db.commit()
        db.refresh(result)

        return result

    # Step 4: Generate and validate resolution.
    try:
        resolution = generate_resolution(
            ticket,
            classification,
            evidence,
        )

        # Validate both resolution output and classification action.
        validation = validate_resolution(
            {
                "root_cause": resolution.root_cause,
                "summary": resolution.summary,
                "recommended_next_action": (
                    classification.recommended_next_action
                ),
                "resolution_steps": resolution.resolution_steps,
                "customer_response": resolution.customer_response,
            },
            evidence,
        )

        # Step 5: Calculate retrieval confidence.
        scores = [
            max(0.0, min(1.0, float(item["score"])))
            for item in evidence
        ]

        confidence = min(
            1.0,
            (
                sum(scores[:3])
                / max(1, min(3, len(scores)))
            )
            * min(1, len(scores) / 2),
        )

        confidence = round(confidence, 3)

        # Step 6: Apply evidence-validation fallback.
        recommended_next_action = (
            classification.recommended_next_action
        )

        if not validation.is_valid:
            validation_reason = (
                "Evidence validation failed; human review required. "
                + "; ".join(validation.errors)
            )

            _apply_resolution_fallback(
                resolution,
                validation_reason,
            )

            # Do not persist an unsupported classification action.
            recommended_next_action = (
                "Human support review required. "
                "Verify the available documentation before responding."
            )

        # Step 7: Apply confidence escalation.
        if confidence < CONFIDENCE_THRESHOLD:
            resolution.escalation_required = True

            if validation.is_valid:
                resolution.escalation_reason = (
                    f"Low retrieval confidence ({confidence:.3f}); "
                    "human review required."
                )

        # Critical tickets always require human review.
        if ticket.priority == "Critical":
            resolution.escalation_required = True

            if validation.is_valid:
                resolution.escalation_reason = (
                    "Critical-priority ticket requires human review."
                )

        # Step 8: Persist AI result.
        result = ticket.ai_result or TicketAIResult(
            ticket_id=ticket.ticket_id
        )

        result.available = True
        result.sentiment = classification.sentiment
        result.intent = classification.intent
        result.recommended_next_action = (
            recommended_next_action
        )
        result.main_issue = classification.main_issue

        result.summary = resolution.summary
        result.root_cause = resolution.root_cause

        result.resolution_steps = json.dumps(
            resolution.resolution_steps,
            ensure_ascii=False,
        )

        result.customer_response = resolution.customer_response

        result.sources = json.dumps(
            [
                source.model_dump()
                for source in resolution.sources
            ],
            ensure_ascii=False,
        )

        result.confidence = confidence
        result.escalation_required = resolution.escalation_required
        result.escalation_reason = resolution.escalation_reason

        # Step 9: Record status transition.
        if result.escalation_required:
            _record_escalation(
                db,
                ticket,
                result.escalation_reason,
            )

        db.add(result)
        db.commit()
        db.refresh(result)

        return result

    except Exception:
        db.rollback()
        db.refresh(ticket)

        result = ticket.ai_result or TicketAIResult(
            ticket_id=ticket.ticket_id
        )

        _safe_fallback(
            result,
            "Resolution generation or validation failed; "
            "human review required.",
        )

        # Generation failure means AI resolution is unavailable.
        result.available = False

        _record_escalation(
            db,
            ticket,
            result.escalation_reason,
        )

        db.add(result)
        db.commit()
        db.refresh(result)

        return result
