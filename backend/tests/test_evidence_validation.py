
import json
import pytest

from unittest.mock import patch

from app.services.evidence_validator import validate_resolution
from app.database import SessionLocal
from app.models import Ticket, TicketAIResult
from app.services.ai_service import analyze_and_resolve
from app.schemas import Classification, Resolution


@pytest.fixture
def login_evidence():
    return [
        {
            "document_name": "password_and_login.md",
            "chunk_id": "chunk_0001",
            "text": (
                "After five consecutive failed login attempts, "
                "the account is temporarily locked for 15 minutes. "
                "Wait for the lockout period to end before trying again. "
                "Support agents must verify account ownership before "
                "changing registered email addresses."
            ),
        }
    ]


def test_documented_lockout_claims_are_accepted(login_evidence):
    resolution = {
        "root_cause": (
            "Account temporarily locked after five consecutive "
            "failed login attempts."
        ),
        "resolution_steps": [
            "Wait 15 minutes before trying again."
        ],
        "customer_response": (
            "Your account may be temporarily locked. "
            "Please wait 15 minutes before trying again."
        ),
    }

    result = validate_resolution(resolution, login_evidence)

    assert result.is_valid is True
    assert result.errors == []


@pytest.mark.parametrize(
    "unsupported_claim",
    [
        "Ask the customer to upload a government ID.",
        "Verify ownership using the last four transaction digits.",
        "Ask the customer to answer a security question.",
        "Manually unlock the account immediately.",
        "Clear browser cache to fix the login problem.",
    ],
)
def test_unsupported_instructions_are_rejected(
    login_evidence,
    unsupported_claim,
):
    resolution = {
        "root_cause": "Account temporarily locked.",
        "resolution_steps": [unsupported_claim],
        "customer_response": (
            "Our support team will investigate your issue."
        ),
    }

    result = validate_resolution(resolution, login_evidence)

    assert result.is_valid is False
    assert len(result.errors) > 0


def test_customer_response_must_use_agent_perspective(login_evidence):
    resolution = {
        "root_cause": "Account temporarily locked.",
        "resolution_steps": [
            "Wait 15 minutes before trying again."
        ],
        "customer_response": (
            "We will wait 15 minutes and try again."
        ),
    }

    result = validate_resolution(resolution, login_evidence)

    assert result.is_valid is False
    assert len(result.errors) > 0


def test_validation_failure_persists_safe_response(client):
    # Create a ticket through the API.
    response = client.post(
        "/api/tickets",
        json={
            "customer_name": "Evidence Test",
            "customer_email": "evidence.test@example.com",
            "subject": "Unable to login after password reset",
            "description": (
                "My account is locked after resetting my password "
                "and I cannot log in."
            ),
        },
    )

    assert response.status_code in (200, 201)

    ticket_id = response.json()["ticket_id"]

    classification = Classification(
        category="Account & Login",
        priority="High",
        sentiment="Negative",
        intent="Resolve login problem",
        main_issue="Account temporarily locked",
        summary="Customer cannot log in.",
        recommended_next_action="Review login issue.",
    )

    unsafe_resolution = Resolution(
        summary="Login issue",
        category="Account & Login",
        priority="High",
        sentiment="Negative",
        root_cause="Account temporarily locked.",
        resolution_steps=[
            "Ask the customer to upload a government ID."
        ],
        customer_response=(
            "Please upload your government ID to unlock your account."
        ),
        sources=[
            {
                "document_name": "password_and_login.md",
                "chunk_id": "chunk_0001",
            }
        ],
        confidence=0.8,
        escalation_required=False,
        escalation_reason=None,
    )

    evidence = [
        {
            "document_name": "password_and_login.md",
            "chunk_id": "chunk_0001",
            "text": (
                "After five consecutive failed login attempts, "
                "the account is temporarily locked for 15 minutes."
            ),
            "score": 0.8,
        }
    ]

    with SessionLocal() as db:
        ticket = (
            db.query(Ticket)
            .filter_by(ticket_id=ticket_id)
            .first()
        )

        assert ticket is not None

        with patch(
            "app.services.ai_service.classify_ticket",
            return_value=classification,
        ), patch(
            "app.services.ai_service.search_chunks",
            return_value=evidence,
        ), patch(
            "app.services.ai_service.generate_resolution",
            return_value=unsafe_resolution,
        ):
            result = analyze_and_resolve(db, ticket)

        # Verify safe fallback in the returned result.
        assert result.available is True
        assert result.escalation_required is True
        assert "Evidence validation failed" in result.escalation_reason

        assert "government ID" not in result.customer_response.lower()
        assert result.resolution_steps == "[]"
        assert result.sources == "[]"

        assert "fully verified root cause" in result.root_cause.lower()
        assert "requires human review" in result.summary.lower()

        assert "account lockout procedure" not in (
            result.recommended_next_action.lower()
        )

    # Verify the actual persisted database record.
    with SessionLocal() as db:
        saved = (
            db.query(TicketAIResult)
            .filter_by(ticket_id=ticket_id)
            .first()
        )

        assert saved is not None
        assert saved.available is True
        assert saved.escalation_required is True

        assert saved.resolution_steps == "[]"
        assert saved.sources == "[]"

        assert "government ID" not in saved.customer_response.lower()
        assert "review your case" in saved.customer_response.lower()

        assert "fully verified root cause" in saved.root_cause.lower()
        assert "requires human review" in saved.summary.lower()

        assert "account lockout procedure" not in (
            saved.recommended_next_action.lower()
        )


def test_rejects_unsupported_unlock_in_recommended_action():
    resolution = {
        "root_cause": "Account temporarily locked.",
        "summary": "Customer cannot log in.",
        "recommended_next_action": "Unlock the account immediately.",
        "resolution_steps": ["Wait for 15 minutes."],
        "customer_response": "Please wait for the lockout period to end.",
    }

    evidence = [
        {
            "text": (
                "After five consecutive failed login attempts, "
                "the account is temporarily locked for 15 minutes. "
                "Wait for the lockout period to end before trying again."
            )
        }
    ]

    result = validate_resolution(resolution, evidence)

    assert result.is_valid is False
    assert any(
        "manual account unlock" in error.lower()
        for error in result.errors
    )


# ---------------------------------------------------------
# Phone Number Verification Regression Tests
# ---------------------------------------------------------


@pytest.fixture
def phone_number_evidence():
    return [
        {
            "document_name": "rag_regression_test.md",
            "chunk_id": "chunk_0001",
            "text": (
                "Customers can update their registered phone number "
                "from Account Settings. "
                "The new phone number must be verified before it "
                "becomes active. "
                "Support agents must not bypass phone number verification."
            ),
        }
    ]


@pytest.mark.parametrize(
    "unsupported_claim",
    [
        "A verification code will be sent to your new number.",
        "The previous number will remain active until verification.",
        "The old number will remain in use until verification.",
    ],
)
def test_unsupported_phone_number_claims_are_rejected(
    phone_number_evidence,
    unsupported_claim,
):
    resolution = {
        "root_cause": "Customer wants to update their phone number.",
        "summary": "Phone number update request.",
        "resolution_steps": [unsupported_claim],
        "customer_response": (
            "Our support team will assist you with the documented process."
        ),
    }

    result = validate_resolution(
        resolution,
        phone_number_evidence,
    )

    assert result.is_valid is False
    assert len(result.errors) > 0


def test_documented_phone_number_update_is_accepted(
    phone_number_evidence,
):
    resolution = {
        "root_cause": "Customer wants to update their registered phone number.",
        "summary": "Phone number update request.",
        "resolution_steps": [
            "Open Account Settings.",
            "Update your registered phone number.",
            "Verify the new phone number before it becomes active.",
        ],
        "customer_response": (
            "You can update your registered phone number from "
            "Account Settings. The new number must be verified "
            "before it becomes active."
        ),
    }

    result = validate_resolution(
        resolution,
        phone_number_evidence,
    )

    assert result.is_valid is True
    assert result.errors == []
