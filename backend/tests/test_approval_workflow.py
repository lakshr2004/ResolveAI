
from app.database import SessionLocal
from app.models import (
    Ticket,
    TicketAIResult,
    TicketHistory,
    AgentNote,
    TicketActionHistory,
)


def create_test_ticket(client, escalation_required=False):
    response = client.post(
        "/api/tickets",
        json={
            "customer_name": "Approval Test",
            "customer_email": "approval@example.com",
            "subject": "Testing approval workflow",
            "description": "Testing AI customer response approval.",
        },
    )

    assert response.status_code == 201

    ticket_id = response.json()["ticket_id"]

    with SessionLocal() as db:
        result = TicketAIResult(
            ticket_id=ticket_id,
            available=True,
            sentiment="Neutral",
            intent="Test intent",
            recommended_next_action="Review response",
            main_issue="Test issue",
            summary="Test summary",
            root_cause="Test root cause",
            resolution_steps='["Step 1"]',
            customer_response="This is a verified test response.",
            sources="[]",
            confidence=0.80,
            escalation_required=escalation_required,
            escalation_reason=(
                "Human review required."
                if escalation_required else None
            ),
            approval_status="Pending",
        )

        db.add(result)
        db.commit()

    return ticket_id


def cleanup_ticket(ticket_id):
    with SessionLocal() as db:
        ticket = db.query(Ticket).filter_by(
            ticket_id=ticket_id
        ).first()

        if ticket:
            db.delete(ticket)
            db.commit()


def test_ai_response_starts_as_pending(client):
    ticket_id = create_test_ticket(client)

    try:
        response = client.get(
            f"/api/tickets/{ticket_id}"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["ai_result"]["approval_status"] == "Pending"
        assert data["status"] == "Open"

    finally:
        cleanup_ticket(ticket_id)


def test_approve_ai_response_resolves_ticket(client):
    ticket_id = create_test_ticket(client)

    try:
        response = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["approval_status"] == "Approved"
        assert data["ticket_status"] == "Resolved"

        with SessionLocal() as db:
            history_count = (
                db.query(TicketHistory)
                .filter_by(
                    ticket_id=ticket_id,
                    new_status="Resolved",
                )
                .count()
            )

            assert history_count == 1

    finally:
        cleanup_ticket(ticket_id)


def test_repeated_approval_does_not_duplicate_history(client):
    ticket_id = create_test_ticket(client)

    try:
        first = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        second = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        assert first.status_code == 200
        assert second.status_code == 200

        assert second.json()["approval_status"] == "Approved"
        assert second.json()["ticket_status"] == "Resolved"
        assert second.json()["message"] == "Response was already approved"

        with SessionLocal() as db:
            history_count = (
                db.query(TicketHistory)
                .filter_by(
                    ticket_id=ticket_id,
                    new_status="Resolved",
                )
                .count()
            )

            assert history_count == 1

    finally:
        cleanup_ticket(ticket_id)


def test_escalated_response_cannot_be_approved(client):
    ticket_id = create_test_ticket(
        client,
        escalation_required=True,
    )

    try:
        response = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        assert response.status_code == 409

        assert "Human review is required" in response.json()["detail"]

        ticket_response = client.get(
            f"/api/tickets/{ticket_id}"
        )

        data = ticket_response.json()

        assert data["ai_result"]["approval_status"] == "Pending"
        assert data["ai_result"]["escalation_required"] is True

    finally:
        cleanup_ticket(ticket_id)


def test_reject_ai_response_successfully(client):
    ticket_id = create_test_ticket(client)

    try:
        response = client.post(
            f"/api/agents/{ticket_id}/reject",
            json={
                "reason": "AI response contains incorrect information."
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["approval_status"] == "Rejected"
        assert data["ticket_status"] == "Open"
        assert data["rejection_reason"] == (
            "AI response contains incorrect information."
        )

        with SessionLocal() as db:
            note = db.query(AgentNote).filter_by(
                ticket_id=ticket_id
            ).first()

            assert note is not None
            assert "incorrect information" in note.note

    finally:
        cleanup_ticket(ticket_id)


def test_rejection_reason_is_mandatory(client):
    ticket_id = create_test_ticket(client)

    try:
        response = client.post(
            f"/api/agents/{ticket_id}/reject",
            json={},
        )

        assert response.status_code == 422

    finally:
        cleanup_ticket(ticket_id)


def test_repeated_rejection_does_not_create_duplicate_notes(client):
    ticket_id = create_test_ticket(client)

    try:
        payload = {
            "reason": "The generated response needs correction."
        }

        first = client.post(
            f"/api/agents/{ticket_id}/reject",
            json=payload,
        )

        second = client.post(
            f"/api/agents/{ticket_id}/reject",
            json={"reason": "Another rejection reason."},
        )

        assert first.status_code == 200
        assert second.status_code == 200

        assert second.json()["message"] == "Response was already rejected"

        with SessionLocal() as db:
            note_count = db.query(AgentNote).filter_by(
                ticket_id=ticket_id
            ).count()

            assert note_count == 1

    finally:
        cleanup_ticket(ticket_id)


def test_approved_response_cannot_be_rejected(client):
    ticket_id = create_test_ticket(client)

    try:
        approval = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        assert approval.status_code == 200

        rejection = client.post(
            f"/api/agents/{ticket_id}/reject",
            json={
                "reason": "Trying to reject an approved response."
            },
        )

        assert rejection.status_code == 409

    finally:
        cleanup_ticket(ticket_id)


def test_escalated_response_cannot_be_rejected(client):
    ticket_id = create_test_ticket(
        client,
        escalation_required=True,
    )

    try:
        response = client.post(
            f"/api/agents/{ticket_id}/reject",
            json={
                "reason": "Trying to reject an escalated response."
            },
        )

        assert response.status_code == 409

    finally:
        cleanup_ticket(ticket_id)


def test_edit_response_preserves_action_history(client):
    ticket_id = create_test_ticket(client)

    try:
        with SessionLocal() as db:
            result = db.query(TicketAIResult).filter_by(
                ticket_id=ticket_id
            ).first()

            original_response = result.customer_response

        updated_response = (
            "Updated customer response after agent review."
        )

        response = client.post(
            f"/api/agents/{ticket_id}/edit-response",
            json={
                "customer_response": updated_response
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["approval_status"] == "Edited"
        assert data["customer_response"] == updated_response

        with SessionLocal() as db:
            history = db.query(TicketActionHistory).filter_by(
                ticket_id=ticket_id,
                action="EDITED",
            ).first()

            assert history is not None
            assert history.previous_response == original_response
            assert history.new_response == updated_response
            assert history.actor == "ResolveAI Admin"

    finally:
        cleanup_ticket(ticket_id)



def test_approval_creates_action_history_without_duplicates(client):
    ticket_id = create_test_ticket(client)

    try:
        with SessionLocal() as db:
            result = db.query(TicketAIResult).filter_by(
                ticket_id=ticket_id
            ).first()

            original_response = result.customer_response

        # First approval
        first = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        assert first.status_code == 200
        assert first.json()["approval_status"] == "Approved"

        # Repeated approval
        second = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        assert second.status_code == 200
        assert second.json()["message"] == "Response was already approved"

        with SessionLocal() as db:
            history = db.query(TicketActionHistory).filter_by(
                ticket_id=ticket_id,
                action="APPROVED",
            ).all()

            assert len(history) == 1

            approval_record = history[0]

            assert approval_record.previous_response == original_response
            assert approval_record.new_response == original_response
            assert approval_record.actor == "ResolveAI Admin"
            assert approval_record.reason is None

    finally:
        cleanup_ticket(ticket_id)

def test_rejection_creates_action_history_without_duplicates(client):
    ticket_id = create_test_ticket(client)

    try:
        with SessionLocal() as db:
            result = (
                db.query(TicketAIResult)
                .filter_by(ticket_id=ticket_id)
                .first()
            )
            original_response = result.customer_response

        payload = {
            "reason": "Response contains unsupported information"
        }

        first = client.post(
            f"/api/agents/{ticket_id}/reject",
            json=payload,
        )

        assert first.status_code == 200
        assert first.json()["approval_status"] == "Rejected"

        second = client.post(
            f"/api/agents/{ticket_id}/reject",
            json=payload,
        )

        assert second.status_code == 200
        assert second.json()["message"] == "Response was already rejected"

        with SessionLocal() as db:
            history = (
                db.query(TicketActionHistory)
                .filter_by(
                    ticket_id=ticket_id,
                    action="REJECTED",
                )
                .all()
            )

            assert len(history) == 1

            rejection_record = history[0]

            assert rejection_record.previous_response == original_response
            assert rejection_record.new_response is None
            assert rejection_record.reason == payload["reason"]
            assert rejection_record.actor == "ResolveAI Admin"

    finally:
        cleanup_ticket(ticket_id)

def test_pending_ticket_cannot_be_directly_resolved(client):
    ticket_id = create_test_ticket(client)

    try:
        response = client.patch(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "Resolved"},
        )

        assert response.status_code == 409
        assert "without approving" in response.json()["detail"]

        with SessionLocal() as db:
            ticket = db.query(Ticket).filter_by(
                ticket_id=ticket_id
            ).first()

            assert ticket.status != "Resolved"

    finally:
        cleanup_ticket(ticket_id)


def test_approved_ticket_can_be_resolved(client):
    ticket_id = create_test_ticket(client)

    try:
        approval = client.post(
            f"/api/agents/{ticket_id}/approve"
        )

        assert approval.status_code == 200

        response = client.patch(
            f"/api/tickets/{ticket_id}/status",
            json={"status": "Resolved"},
        )

        assert response.status_code == 200

        with SessionLocal() as db:
            ticket = db.query(Ticket).filter_by(
                ticket_id=ticket_id
            ).first()

            assert ticket.status == "Resolved"

    finally:
        cleanup_ticket(ticket_id)        


def test_action_history_endpoint_returns_audit_records(client):
    ticket_id = create_test_ticket(client)

    try:
        edit_response = client.post(
            f"/api/agents/{ticket_id}/edit-response",
            json={
                "customer_response": (
                    "Updated and verified customer response."
                )
            },
        )

        assert edit_response.status_code == 200

        response = client.get(
            f"/api/tickets/{ticket_id}/action-history"
        )

        assert response.status_code == 200

        history = response.json()

        assert len(history) == 1
        assert history[0]["action"] == "EDITED"
        assert history[0]["previous_response"] == (
            "This is a verified test response."
        )
        assert history[0]["new_response"] == (
            "Updated and verified customer response."
        )
        assert history[0]["actor"] == "ResolveAI Admin"
        assert history[0]["reason"] is None
        assert "created_at" in history[0]

    finally:
        cleanup_ticket(ticket_id)

