
from sqlalchemy import text

from app.database import Base, engine, SessionLocal
from app.models import Ticket, TicketAIResult, TicketHistory, AgentNote


def test_ticket_deletion_cascades_to_related_records(client):
    Base.metadata.create_all(bind=engine)

    ticket_id = "RAI-CASCADE-TEST"

    with SessionLocal() as db:
        ticket = Ticket(
            ticket_id=ticket_id,
            customer_name="Cascade Test",
            customer_email="cascade@example.com",
            subject="Test cascade deletion",
            description="Testing related record deletion."
        )

        db.add(ticket)
        db.flush()

        db.add(TicketAIResult(
            ticket_id=ticket_id,
            available=True,
            sentiment="Negative",
            intent="Test intent",
            confidence=0.5,
            escalation_required=False,
            approval_status="Pending"
        ))

        db.add(TicketHistory(
            ticket_id=ticket_id,
            old_status="Open",
            new_status="In Progress",
            note="Cascade test"
        ))

        db.add(AgentNote(
            ticket_id=ticket_id,
            note="Temporary cascade deletion test"
        ))

        db.commit()

        # Delete parent directly using SQL.
        # This bypasses SQLAlchemy ORM relationship cascades.
        db.execute(
            text("DELETE FROM tickets WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        )
        db.commit()

        # Verify database-level foreign-key cascades.
        ai_count = db.query(TicketAIResult).filter_by(
            ticket_id=ticket_id
        ).count()

        history_count = db.query(TicketHistory).filter_by(
            ticket_id=ticket_id
        ).count()

        notes_count = db.query(AgentNote).filter_by(
            ticket_id=ticket_id
        ).count()

        assert ai_count == 0
        assert history_count == 0
        assert notes_count == 0
