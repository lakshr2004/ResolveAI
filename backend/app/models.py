
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    Index,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now():
    return datetime.now(timezone.utc)


# =========================================================
# USER MODEL - AUTHENTICATION & AUTHORIZATION
# =========================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default="Agent",
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
        onupdate=now,
    )


# =========================================================
# EXISTING TICKET MODEL
# =========================================================

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)

    ticket_id: Mapped[str] = mapped_column(
        String(24),
        unique=True,
        index=True,
        default=lambda: "RAI-" + uuid.uuid4().hex[:8].upper(),
    )

    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)

    category: Mapped[str] = mapped_column(
        String(50),
        default="General Inquiry",
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        default="Medium",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="Open",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
        onupdate=now,
    )

    ai_result = relationship(
        "TicketAIResult",
        back_populates="ticket",
        uselist=False,
        cascade="all, delete-orphan",
    )

    history = relationship(
        "TicketHistory",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketHistory.created_at",
    )

    notes = relationship(
        "AgentNote",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )


# =========================================================
# TICKET AI RESULT MODEL
# =========================================================

class TicketAIResult(Base):
    __tablename__ = "ticket_ai_results"

    id: Mapped[int] = mapped_column(primary_key=True)

    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    available: Mapped[bool] = mapped_column(default=False)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(120), nullable=True)

    recommended_next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_issue: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0)
    escalation_required: Mapped[bool] = mapped_column(default=True)

    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    approval_status: Mapped[str] = mapped_column(
        String(20),
        default="Pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    ticket = relationship("Ticket", back_populates="ai_result")


# =========================================================
# TICKET HISTORY MODEL
# =========================================================

class TicketHistory(Base):
    __tablename__ = "ticket_history"

    id: Mapped[int] = mapped_column(primary_key=True)

    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        index=True,
    )

    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    ticket = relationship("Ticket", back_populates="history")


# =========================================================
# KNOWLEDGE DOCUMENT MODEL
# =========================================================

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    document_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    filename: Mapped[str] = mapped_column(String(255))

    content_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="Indexed",
    )

    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )


# =========================================================
# AGENT NOTES MODEL
# =========================================================

class AgentNote(Base):
    __tablename__ = "agent_notes"

    id: Mapped[int] = mapped_column(primary_key=True)

    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        index=True,
    )

    note: Mapped[str] = mapped_column(Text)

    author: Mapped[str] = mapped_column(
        String(120),
        default="Support Agent",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    ticket = relationship("Ticket", back_populates="notes")


# =========================================================
# TICKET ACTION HISTORY MODEL
# =========================================================

class TicketActionHistory(Base):
    __tablename__ = "ticket_action_history"

    id: Mapped[int] = mapped_column(primary_key=True)

    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    previous_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    new_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    actor: Mapped[str] = mapped_column(
        String(120),
        default="Support Agent",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )


# =========================================================
# EXISTING INDEX
# =========================================================

Index(
    "ix_ticket_category_priority",
    Ticket.category,
    Ticket.priority,
)
