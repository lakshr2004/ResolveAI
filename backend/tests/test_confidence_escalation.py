import pytest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.models import Ticket, TicketAIResult, TicketHistory
from app.services.ai_service import analyze_and_resolve
from app.database import SessionLocal


def test_low_confidence_triggers_escalation():
    with SessionLocal() as db:
        ticket = Ticket(
            ticket_id="RAI-LOWCONF-001",
            customer_name="Test Customer",
            customer_email="lowconf@example.com",
            subject="Test low confidence escalation",
            description="Testing low retrieval confidence."
        )

        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        classification = SimpleNamespace(
            category="Account & Login",
            priority="High",
            sentiment="Negative",
            intent="Login assistance",
            main_issue="Cannot login",
            summary="Login issue",
            recommended_next_action="Verify account"
        )

        resolution = SimpleNamespace(
            summary="Login issue",
            root_cause="Unknown",
            resolution_steps=["Verify account"],
            customer_response="Support will review your case.",
            sources=[],
            escalation_required=False,
            escalation_reason=None
        )

        evidence = [{
            "score": 0.60,
            "document_name": "test.md",
            "chunk_id": "chunk_0001",
            "text": "Test evidence"
        }]

        try:
            with patch(
                "app.services.ai_service.classify_ticket",
                return_value=classification
            ), patch(
                "app.services.ai_service.search_chunks",
                return_value=evidence
            ), patch(
                "app.services.ai_service.generate_resolution",
                return_value=resolution
            ):
                result = analyze_and_resolve(db, ticket)

                assert result.confidence == 0.300
                assert result.escalation_required is True
                assert "Low retrieval confidence" in result.escalation_reason
                assert ticket.status == "Escalated"

        finally:
            db.delete(ticket)
            db.commit()




@pytest.mark.parametrize(
    "scores, expected_confidence, expected_escalation",
    [
        ([0.998], 0.499, True),
        ([1.000], 0.500, False),
        ([0.700, 0.700], 0.700, False),
    ],
)
def test_confidence_threshold_boundaries(
    scores,
    expected_confidence,
    expected_escalation,
):
    with SessionLocal() as db:
        ticket_id = f"RAI-BOUNDARY-{uuid.uuid4().hex[:8].upper()}"

        ticket = Ticket(
            ticket_id=ticket_id,
            customer_name="Boundary Test",
            customer_email="boundary@example.com",
            subject="Confidence boundary test",
            description="Testing confidence threshold boundaries.",
        )

        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        classification = SimpleNamespace(
            category="Account & Login",
            priority="High",
            sentiment="Negative",
            intent="Login assistance",
            main_issue="Cannot login",
            summary="Login issue",
            recommended_next_action="Verify account",
        )

        resolution = SimpleNamespace(
            summary="Login issue",
            root_cause="Unknown",
            resolution_steps=["Verify account"],
            customer_response="Support will review your case.",
            sources=[],
            escalation_required=False,
            escalation_reason=None,
        )

        evidence = [
            {
                "score": score,
                "document_name": "test.md",
                "chunk_id": f"chunk_{index:04d}",
                "text": "Test evidence",
            }
            for index, score in enumerate(scores, start=1)
        ]

        try:
            with patch(
                "app.services.ai_service.classify_ticket",
                return_value=classification,
            ), patch(
                "app.services.ai_service.search_chunks",
                return_value=evidence,
            ), patch(
                "app.services.ai_service.generate_resolution",
                return_value=resolution,
            ):
                result = analyze_and_resolve(db, ticket)

                assert result.confidence == expected_confidence
                assert result.escalation_required is expected_escalation

                if expected_escalation:
                    assert ticket.status == "Escalated"
                else:
                    assert ticket.status == "Open"

        finally:
            db.delete(ticket)
            db.commit()


@pytest.mark.parametrize(
    "initial_status, expected_history_count",
    [
        ("Open", 1),
        ("Escalated", 0),
        ("Resolved", 0),
    ],
)
def test_escalation_history_transition(
    initial_status,
    expected_history_count,
):
    with SessionLocal() as db:
        ticket_id = f"RAI-HISTORY-{uuid.uuid4().hex[:8].upper()}"

        ticket = Ticket(
            ticket_id=ticket_id,
            customer_name="History Test",
            customer_email="history@example.com",
            subject="Testing escalation history",
            description="Testing ticket escalation history records.",
            status=initial_status,
        )

        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        classification = SimpleNamespace(
            category="Account & Login",
            priority="High",
            sentiment="Negative",
            intent="Login assistance",
            main_issue="Cannot login",
            summary="Login issue",
            recommended_next_action="Verify account",
        )

        resolution = SimpleNamespace(
            summary="Login issue",
            root_cause="Unknown",
            resolution_steps=["Verify account"],
            customer_response="Support will review your case.",
            sources=[],
            escalation_required=False,
            escalation_reason=None,
        )

        evidence = [
            {
                "score": 0.60,
                "document_name": "test.md",
                "chunk_id": "chunk_0001",
                "text": "Test evidence",
            }
        ]

        try:
            with patch(
                "app.services.ai_service.classify_ticket",
                return_value=classification,
            ), patch(
                "app.services.ai_service.search_chunks",
                return_value=evidence,
            ), patch(
                "app.services.ai_service.generate_resolution",
                return_value=resolution,
            ):
                result = analyze_and_resolve(db, ticket)

                db.refresh(ticket)

                history_count = (
                    db.query(TicketHistory)
                    .filter_by(ticket_id=ticket_id)
                    .count()
                )

                assert result.escalation_required is True
                assert history_count == expected_history_count

                if initial_status == "Open":
                    assert ticket.status == "Escalated"

                elif initial_status == "Escalated":
                    assert ticket.status == "Escalated"

                elif initial_status == "Resolved":
                    assert ticket.status == "Resolved"

        finally:
            db.delete(ticket)
            db.commit()
