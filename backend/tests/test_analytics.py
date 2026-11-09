
from uuid import uuid4


def create_ticket(client):
    unique_id = uuid4().hex[:8]

    payload = {
        "customer_name": "Analytics Test",
        "customer_email": f"analytics_{unique_id}@example.com",
        "subject": "Analytics test ticket",
        "description": "Testing analytics endpoint functionality."
    }

    response = client.post("/api/tickets", json=payload)

    assert response.status_code == 201
    return response.json()


def test_analytics_overview_shape(client):
    response = client.get("/api/analytics/overview")

    assert response.status_code == 200

    data = response.json()

    expected_keys = [
        "total_tickets",
        "open_tickets",
        "resolved_tickets",
        "escalated_tickets",
        "critical_tickets",
        "average_resolution_hours",
        "ai_handled",
        "human_escalated",
        "recent_tickets",
    ]

    for key in expected_keys:
        assert key in data


def test_categories_analytics(client):
    response = client.get("/api/analytics/categories")

    assert response.status_code == 200
    assert isinstance(response.json(), list)

    for item in response.json():
        assert "name" in item
        assert "value" in item
        assert isinstance(item["value"], int)


def test_priorities_analytics(client):
    response = client.get("/api/analytics/priorities")

    assert response.status_code == 200
    assert isinstance(response.json(), list)

    for item in response.json():
        assert "name" in item
        assert "value" in item
        assert isinstance(item["value"], int)


def test_trends_default_range(client):
    response = client.get("/api/analytics/trends")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 7

    for item in data:
        assert "date" in item
        assert "created" in item
        assert "resolved" in item
        assert isinstance(item["created"], int)
        assert isinstance(item["resolved"], int)


def test_trends_custom_ranges(client):
    for days in [7, 30, 90]:
        response = client.get(
            f"/api/analytics/trends?days={days}"
        )

        assert response.status_code == 200
        assert len(response.json()) == days


def test_trends_invalid_ranges(client):
    for days in [0, 91, -1]:
        response = client.get(
            f"/api/analytics/trends?days={days}"
        )

        assert response.status_code == 422


def test_trends_created_ticket_count(client):
    ticket = create_ticket(client)

    response = client.get("/api/analytics/trends?days=7")

    assert response.status_code == 200

    data = response.json()

    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date().isoformat()

    today_data = next(
        (item for item in data if item["date"] == today),
        None
    )

    assert today_data is not None
    assert today_data["created"] >= 1



def test_sla_analytics_response_shape(client):
    response = client.get("/api/analytics/sla")

    assert response.status_code == 200

    data = response.json()

    assert "total_tickets" in data
    assert "evaluated_tickets" in data
    assert "within_sla" in data
    assert "breached" in data
    assert "unknown" in data
    assert "compliance_percentage" in data
    assert "sla_targets" in data
    assert "tickets" in data


def test_sla_targets(client):
    response = client.get("/api/analytics/sla")

    assert response.status_code == 200

    targets = response.json()["sla_targets"]

    assert targets == {
        "Critical": 4,
        "High": 12,
        "Medium": 24,
        "Low": 48,
    }


def test_sla_compliance_calculation(client):
    response = client.get("/api/analytics/sla")

    assert response.status_code == 200

    data = response.json()

    evaluated = data["within_sla"] + data["breached"]

    assert evaluated == data["evaluated_tickets"]

    if evaluated:
        expected = round(
            data["within_sla"] / evaluated * 100,
            2,
        )
        assert data["compliance_percentage"] == expected
    else:
        assert data["compliance_percentage"] is None


def test_sla_ticket_fields(client):
    response = client.get("/api/analytics/sla")

    assert response.status_code == 200

    for ticket in response.json()["tickets"]:
        assert ticket["sla_target_hours"] > 0
        assert ticket["elapsed_hours"] >= 0
        assert isinstance(ticket["remaining_hours"], (int, float))
        assert ticket["sla_status"] in ["Within SLA", "Breached"]



def test_approval_analytics_response_shape(client):
    response = client.get("/api/analytics/approvals")

    assert response.status_code == 200

    data = response.json()

    assert "total_responses" in data
    assert "status_distribution" in data
    assert "approval_rate" in data
    assert "rejection_rate" in data
    assert "total_actions" in data
    assert "action_distribution" in data


def test_approval_analytics_status_counts(client):
    response = client.get("/api/analytics/approvals")

    assert response.status_code == 200

    data = response.json()
    statuses = data["status_distribution"]

    assert set(statuses) == {
        "Approved",
        "Rejected",
        "Edited",
        "Pending",
    }

    assert sum(statuses.values()) == data["total_responses"]


def test_approval_analytics_action_counts(client):
    response = client.get("/api/analytics/approvals")

    assert response.status_code == 200

    data = response.json()
    actions = data["action_distribution"]

    assert set(actions) == {
        "APPROVED",
        "REJECTED",
        "EDITED",
    }

    assert sum(actions.values()) == data["total_actions"]


def test_support_activity_analytics_response_shape(client):
    response = client.get("/api/analytics/support-activity")

    assert response.status_code == 200

    data = response.json()

    expected_keys = [
        "total_support_actions",
        "action_distribution",
        "actions_by_actor",
        "total_internal_notes",
        "notes_by_author",
        "total_resolved_tickets",
        "total_escalated_tickets",
        "individual_agent_performance_available",
        "limitation",
    ]

    for key in expected_keys:
        assert key in data

    assert data["individual_agent_performance_available"] is False


def test_support_activity_action_counts(client):
    response = client.get("/api/analytics/support-activity")

    assert response.status_code == 200

    data = response.json()

    actions = data["action_distribution"]

    assert set(actions) == {
        "APPROVED",
        "REJECTED",
        "EDITED",
    }

    assert sum(actions.values()) == data["total_support_actions"]

    for actor, metrics in data["actions_by_actor"].items():
        assert (
            metrics["APPROVED"]
            + metrics["REJECTED"]
            + metrics["EDITED"]
            == metrics["total_actions"]
        )


def test_support_activity_internal_notes(client):
    response = client.get("/api/analytics/support-activity")

    assert response.status_code == 200

    data = response.json()

    assert sum(
        data["notes_by_author"].values()
    ) == data["total_internal_notes"]

    assert isinstance(data["notes_by_author"], dict)
    assert isinstance(data["actions_by_actor"], dict)
def test_trends_counts_resolution_of_old_ticket(client):
    from datetime import datetime, timedelta, timezone

    from app.database import get_db
    from app.models import Ticket, TicketHistory

    # Capture baseline analytics before creating the test ticket
    baseline_response = client.get("/api/analytics/trends?days=7")

    assert baseline_response.status_code == 200

    today = datetime.now(timezone.utc).date().isoformat()

    baseline_today = next(
        item for item in baseline_response.json()
        if item["date"] == today
    )

    baseline_created = baseline_today["created"]
    baseline_resolved = baseline_today["resolved"]

    # Create a new ticket
    ticket_data = create_ticket(client)

    db_generator = get_db()
    db = next(db_generator)

    try:
        ticket = (
            db.query(Ticket)
            .filter(Ticket.ticket_id == ticket_data["ticket_id"])
            .first()
        )

        assert ticket is not None

        # Move ticket creation date 10 days into the past
        ticket.created_at = (
            datetime.now(timezone.utc) - timedelta(days=10)
        )

        # Insert a resolution event today
        db.add(
            TicketHistory(
                ticket_id=ticket.ticket_id,
                old_status="Open",
                new_status="Resolved",
                note="Regression test resolution",
                created_at=datetime.now(timezone.utc),
            )
        )

        db.commit()

    finally:
        db.close()
        db_generator.close()

    # Verify updated trends
    response = client.get("/api/analytics/trends?days=7")

    assert response.status_code == 200

    today_data = next(
        item for item in response.json()
        if item["date"] == today
    )

    # Old ticket must not increase today's creation count
    assert today_data["created"] == baseline_created

    # Its resolution event must increase today's resolution count
    assert today_data["resolved"] == baseline_resolved + 1


def test_sla_exact_deadline_is_breached(client):
    from datetime import datetime, timedelta, timezone

    from app.database import get_db
    from app.models import Ticket, TicketHistory

    ticket_data = create_ticket(client)

    db_generator = get_db()
    db = next(db_generator)

    try:
        ticket = (
            db.query(Ticket)
            .filter(Ticket.ticket_id == ticket_data["ticket_id"])
            .first()
        )

        now = datetime.now(timezone.utc)
        ticket.priority = "Critical"
        ticket.status = "Resolved"
        ticket.created_at = now - timedelta(hours=5)

        db.add(
            TicketHistory(
                ticket_id=ticket.ticket_id,
                old_status="Open",
                new_status="Resolved",
                note="Exact SLA deadline test",
                created_at=now - timedelta(hours=1),
            )
        )

        db.commit()

        ticket_id = ticket.ticket_id

    finally:
        db.close()
        db_generator.close()

    response = client.get("/api/analytics/sla")

    assert response.status_code == 200

    result = next(
        item for item in response.json()["tickets"]
        if item["ticket_id"] == ticket_id
    )

    assert result["sla_target_hours"] == 4
    assert result["elapsed_hours"] == 4.0
    assert result["remaining_hours"] == 0.0
    assert result["sla_status"] == "Breached"


def test_sla_missing_resolution_history_is_unknown(client):
    from datetime import datetime, timedelta, timezone

    from app.database import get_db
    from app.models import Ticket

    ticket_data = create_ticket(client)

    db_generator = get_db()
    db = next(db_generator)

    try:
        ticket = (
            db.query(Ticket)
            .filter(Ticket.ticket_id == ticket_data["ticket_id"])
            .first()
        )

        ticket.status = "Resolved"
        ticket.created_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )

        db.commit()

        ticket_id = ticket.ticket_id

    finally:
        db.close()
        db_generator.close()

    response = client.get("/api/analytics/sla")

    assert response.status_code == 200

    data = response.json()

    assert data["unknown"] >= 1

    assert not any(
        item["ticket_id"] == ticket_id
        for item in data["tickets"]
    )


def test_overview_ai_metrics(client):
    from app.database import get_db
    from app.models import Ticket, TicketAIResult

    # Create two independent tickets
    normal_ticket = create_ticket(client)
    escalated_ticket = create_ticket(client)

    db_generator = get_db()
    db = next(db_generator)

    try:
        # AI processed without escalation
        db.add(
            TicketAIResult(
                ticket_id=normal_ticket["ticket_id"],
                available=True,
                escalation_required=False,
            )
        )

        # AI processed with escalation required
        db.add(
            TicketAIResult(
                ticket_id=escalated_ticket["ticket_id"],
                available=True,
                escalation_required=True,
            )
        )

        db.commit()

    finally:
        db.close()
        db_generator.close()

    response = client.get("/api/analytics/overview")

    assert response.status_code == 200

    data = response.json()

    assert data["ai_processed"] >= 2
    assert data["ai_processed_without_escalation"] >= 1
    assert data["ai_escalation_required"] >= 1


def test_overview_legacy_metric_compatibility(client):
    response = client.get("/api/analytics/overview")

    assert response.status_code == 200

    data = response.json()

    assert data["ai_handled"] == data["ai_processed_without_escalation"]
    assert data["human_escalated"] == data["ai_escalation_required"]
