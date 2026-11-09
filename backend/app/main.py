
import json
import logging

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Query,
)

from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.config import settings

from app.database import (
    Base,
    engine,
    get_db,
    SessionLocal,
)

from app.models import (
    TicketAIResult,
    Ticket,
    TicketHistory,
    KnowledgeDocument,
    AgentNote,
    TicketActionHistory,
    User,
)

from app.schemas import (
    TicketCreate,
    StatusUpdate,
    NoteCreate,
    EditResponse,
    RejectResponse,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)

from app.services.document_service import (
    ingest_document,
    remove_document,
)

from app.services.vector_store import (
    search_chunks,
    client,
)

from app.security import (
    verify_password,
    hash_password,
    create_access_token,
    require_roles,
)

from app.services.ai_service import analyze_and_resolve
from app.services.auth_service import bootstrap_admin


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logger = logging.getLogger("resolveai")


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()

    try:
        admin = bootstrap_admin(db)

        logger.info(
            "Admin bootstrap completed for: %s",
            admin.email,
        )
    finally:
        db.close()

    yield


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="ResolveAI API",
    version="1.1.0",
    description="AI-powered Support Ticket Resolution Copilot",
    lifespan=lifespan,
)


# --------------------------------------------------
# CORS CONFIGURATION
# --------------------------------------------------

origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
    ],
)

# --------------------------------------------------
# REQUEST BODY SIZE LIMIT MIDDLEWARE
# --------------------------------------------------
# --------------------------------------------------
# REQUEST BODY SIZE LIMIT MIDDLEWARE
# --------------------------------------------------

class RequestBodyTooLarge(Exception):
    pass


def contains_body_limit_exception(exc):

    if isinstance(exc, RequestBodyTooLarge):
        return True

    if isinstance(exc, BaseExceptionGroup):
        return any(
            contains_body_limit_exception(item)
            for item in exc.exceptions
        )

    return False


class RequestBodyLimitMiddleware:

    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def secure_send(message):

            nonlocal response_started

            if message["type"] == "http.response.start":

                response_started = True

                headers = list(message.get("headers", []))

                security_headers = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"strict-origin-when-cross-origin",
                    b"permissions-policy": (
                        b"camera=(), microphone=(), geolocation=()"
                    ),
                }

                existing = {
                    key.lower()
                    for key, _ in headers
                }

                for key, value in security_headers.items():
                    if key not in existing:
                        headers.append((key, value))

                message["headers"] = headers

            await send(message)

        content_lengths = [
            value
            for key, value in scope.get("headers", [])
            if key.lower() == b"content-length"
        ]

        if len(content_lengths) > 1:
            response = JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header."},
            )
            await response(scope, receive, secure_send)
            return

        if content_lengths:

            try:
                content_length = int(content_lengths[0])

                if content_length < 0:
                    raise ValueError

            except ValueError:
                response = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )
                await response(scope, receive, secure_send)
                return

            if content_length > self.max_body_bytes:

                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
                await response(scope, receive, secure_send)
                return

        received_bytes = 0

        async def limited_receive():

            nonlocal received_bytes

            message = await receive()

            if message["type"] == "http.request":

                received_bytes += len(message.get("body", b""))

                if received_bytes > self.max_body_bytes:
                    raise RequestBodyTooLarge()

            return message

        try:
            await self.app(scope, limited_receive, secure_send)

        except BaseException as exc:

            if not contains_body_limit_exception(exc):
                raise

            if not response_started:

                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )

                await response(scope, receive, secure_send)


app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_bytes=settings.max_request_body_mb * 1024 * 1024,
)
# --------------------------------------------------
# SECURITY HEADERS MIDDLEWARE
# --------------------------------------------------

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)

    response.headers.setdefault(
        "X-Content-Type-Options",
        "nosniff",
    )

    response.headers.setdefault(
        "X-Frame-Options",
        "DENY",
    )

    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin",
    )

    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )

    return response


# --------------------------------------------------
# SERIALIZATION HELPERS
# --------------------------------------------------

def safe_json_loads(value, fallback=None):
    """
    Safely deserialize JSON stored in database fields.
    """

    if fallback is None:
        fallback = []

    if not value:
        return fallback

    try:
        return json.loads(value)

    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Could not deserialize stored JSON value"
        )
        return fallback


def ai_out(result):
    """
    Convert TicketAIResult SQLAlchemy object into API response.
    """

    if not result:
        return None

    return {
        "available": result.available,
        "sentiment": result.sentiment,
        "intent": result.intent,
        "recommended_next_action": result.recommended_next_action,
        "main_issue": result.main_issue,
        "summary": result.summary,
        "root_cause": result.root_cause,
        "resolution_steps": safe_json_loads(
            result.resolution_steps,
            [],
        ),
        "customer_response": result.customer_response,
        "sources": safe_json_loads(
            result.sources,
            [],
        ),
        "confidence": result.confidence,
        "escalation_required": result.escalation_required,
        "escalation_reason": result.escalation_reason,
        "approval_status": result.approval_status,
    }



def ticket_out(ticket, current_user: User):
    """
    Serialize ticket data according to the authenticated user's role.

    Admin and Agent:
        Full ticket information, customer details and internal notes.

    Viewer:
        Ticket information without customer PII or internal notes.
    """

    is_privileged = current_user.role in ("Admin", "Agent")

    response = {
        "ticket_id": ticket.ticket_id,
        "customer_name": ticket.customer_name if is_privileged else None,
        "customer_email": ticket.customer_email if is_privileged else None,
        "subject": ticket.subject,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "ai_result": ai_out(ticket.ai_result)
        if ticket.ai_result
        else None,
        "notes": [],
    }

    # Internal notes are visible only to Admin and Agent.
    if is_privileged:
        response["notes"] = [
            {
                "note": note.note,
                "author": note.author,
                "created_at": note.created_at,
            }
            for note in ticket.notes
        ]

    return response


def get_ticket_or_404(db, ticket_id):
    """
    Retrieve ticket or raise HTTP 404.
    """

    ticket = (
        db.query(Ticket)
        .filter_by(ticket_id=ticket_id)
        .first()
    )

    if not ticket:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    return ticket


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "resolveai-api",
    }


# --------------------------------------------------
# SYSTEM HEALTH - ADMIN ONLY
# --------------------------------------------------

@app.get("/api/system/status")
def system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin")
    ),
):
    # Database connectivity check
    try:
        db.execute(text("SELECT 1"))
        database_status = "connected"

    except Exception:
        logger.exception("Database health check failed")
        database_status = "unavailable"

    # Qdrant connectivity check
    try:
        client().get_collections()
        qdrant_status = "connected"

    except Exception:
        logger.exception("Qdrant health check failed")
        qdrant_status = "unavailable"

    return {
        "api": "healthy",
        "database": database_status,
        "qdrant": qdrant_status,
        "groq_configured": bool(settings.groq_api_key),
        "model": settings.groq_model,
        "embedding_model": settings.embedding_model,
    }


# --------------------------------------------------
# CREATE TICKET - ADMIN / AGENT
# --------------------------------------------------

@app.post("/api/tickets", status_code=201)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Agent")
    ),
):
    try:
        ticket = Ticket(**payload.model_dump())

        db.add(ticket)
        db.flush()

        history = TicketHistory(
            ticket_id=ticket.ticket_id,
            old_status=None,
            new_status="Open",
            note="Ticket created",
        )

        db.add(history)

        db.commit()
        db.refresh(ticket)

        return ticket_out(ticket, current_user)

    except Exception:
        db.rollback()

        logger.exception("Ticket creation failed")

        raise HTTPException(
            status_code=500,
            detail="Ticket could not be created",
        )


# --------------------------------------------------
# LIST TICKETS - ALL AUTHENTICATED ROLES
# --------------------------------------------------

@app.get("/api/tickets")
def list_tickets(
    q: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Agent", "Viewer")
    ),
):
    query = db.query(Ticket)

    if q:
        search_term = f"%{q.strip()}%"

        query = query.filter(
            (Ticket.ticket_id.ilike(search_term))
            | (Ticket.subject.ilike(search_term))
            | (Ticket.customer_email.ilike(search_term))
            | (Ticket.customer_name.ilike(search_term))
        )

    if status:
        query = query.filter(Ticket.status == status)

    if priority:
        query = query.filter(Ticket.priority == priority)

    if category:
        query = query.filter(Ticket.category == category)

    total = query.count()

    items = (
        query
        .order_by(Ticket.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            ticket_out(ticket, current_user)
            for ticket in items
        ],
        "total": total,
    }


# --------------------------------------------------
# GET SINGLE TICKET - ALL AUTHENTICATED ROLES
# --------------------------------------------------

@app.get("/api/tickets/{ticket_id}")
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Agent", "Viewer")
    ),
):
    ticket = get_ticket_or_404(db, ticket_id)

    return ticket_out(ticket, current_user)


# --------------------------------------------------
# UPDATE TICKET STATUS - ADMIN / AGENT
# --------------------------------------------------

@app.patch("/api/tickets/{ticket_id}/status")
def update_status(
    ticket_id: str,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Agent")
    ),
):
    ticket = get_ticket_or_404(db, ticket_id)

    old_status = ticket.status
    new_status = payload.status

    # Prevent direct resolution without agent approval.
    if new_status == "Resolved":
        result = ticket.ai_result

        if not result or result.approval_status != "Approved":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ticket cannot be resolved without "
                    "approving the AI response"
                ),
            )

    if old_status == new_status:
        return ticket_out(ticket, current_user)

    try:
        ticket.status = new_status

        history = TicketHistory(
            ticket_id=ticket.ticket_id,
            old_status=old_status,
            new_status=new_status,
            note=payload.note or "Updated by support agent",
        )

        db.add(history)

        db.commit()
        db.refresh(ticket)

        return ticket_out(ticket, current_user)

    except Exception:
        db.rollback()

        logger.exception("Ticket status update failed")

        raise HTTPException(
            status_code=500,
            detail="Ticket status could not be updated",
        )


# --------------------------------------------------
# TICKET HISTORY - ALL AUTHENTICATED ROLES
# --------------------------------------------------

@app.get("/api/tickets/{ticket_id}/history")
def ticket_history(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Agent", "Viewer")
    ),
):
    get_ticket_or_404(db, ticket_id)

    rows = (
        db.query(TicketHistory)
        .filter_by(ticket_id=ticket_id)
        .order_by(TicketHistory.created_at)
        .all()
    )

    return [
        {
            "old_status": row.old_status,
            "new_status": row.new_status,
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in rows
    ]


# --------------------------------------------------
# TICKET ACTION AUDIT HISTORY - ADMIN / AGENT
# --------------------------------------------------

@app.get("/api/tickets/{ticket_id}/action-history")
def ticket_action_history(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Agent")
    ),
):
    get_ticket_or_404(db, ticket_id)

    rows = (
        db.query(TicketActionHistory)
        .filter_by(ticket_id=ticket_id)
        .order_by(TicketActionHistory.created_at.asc())
        .all()
    )

    return [
        {
            "id": row.id,
            "action": row.action,
            "previous_response": row.previous_response,
            "new_response": row.new_response,
            "reason": row.reason,
            "actor": row.actor,
            "created_at": row.created_at,
        }
        for row in rows
    ]


# --------------------------------------------------
# AI ANALYSIS
# --------------------------------------------------

@app.post("/api/ai/analyze/{ticket_id}")
def analyze(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent")),
):
    ticket = get_ticket_or_404(db, ticket_id)

    try:
        result = analyze_and_resolve(db, ticket)
        return ai_out(result)

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        logger.exception("AI analysis failed for ticket %s", ticket_id)
        raise HTTPException(
            status_code=503,
            detail="AI analysis failed. Check Groq, embedding and Qdrant configuration.",
        )


# --------------------------------------------------
# AI RESOLUTION
# --------------------------------------------------

@app.post("/api/ai/resolve/{ticket_id}")
def resolve(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent")),
):
    return analyze(ticket_id, db)


# --------------------------------------------------
# GET AI RESULT
# --------------------------------------------------

@app.get("/api/ai/result/{ticket_id}")
def ai_result(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    ticket = get_ticket_or_404(db, ticket_id)
    return ai_out(ticket.ai_result)


# --------------------------------------------------
# KNOWLEDGE DOCUMENT UPLOAD
# --------------------------------------------------


@app.post("/api/knowledge/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    filename = Path(file.filename or "upload").name
    extension = Path(filename).suffix.lower()

    allowed_mime_types = {
        ".pdf": {"application/pdf"},
        ".txt": {"text/plain"},
        ".md": {"text/markdown", "text/plain"},
    }

    if extension not in allowed_mime_types:
        await file.close()
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload PDF, TXT or Markdown.",
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()

    if content_type not in allowed_mime_types[extension]:
        await file.close()
        raise HTTPException(
            status_code=400,
            detail="File MIME type does not match its extension.",
        )

    max_size = settings.max_upload_mb * 1024 * 1024

    try:
        # Read only one byte beyond the configured limit.
        content = await file.read(max_size + 1)

        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail="File exceeds upload limit.",
            )

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        document, created = ingest_document(
            db,
            filename,
            content,
        )

        return {
            "document_id": document.document_id,
            "filename": document.filename,
            "status": document.status,
            "chunk_count": document.chunk_count,
            "duplicate": not created,
        }

    except ValueError as error:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        logger.exception(
            "Document ingestion failed: %s",
            filename,
        )
        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed. Check server logs.",
        )

    finally:
        await file.close()


# --------------------------------------------------
# LIST KNOWLEDGE DOCUMENTS
# --------------------------------------------------

@app.get("/api/knowledge/documents")
def documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    docs = (
        db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )

    return [
        {
            "document_id": document.document_id,
            "filename": document.filename,
            "status": document.status,
            "chunk_count": document.chunk_count,
            "created_at": document.created_at,
        }
        for document in docs
    ]


# --------------------------------------------------
# DELETE KNOWLEDGE DOCUMENT
# --------------------------------------------------

@app.delete("/api/knowledge/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    document = (
        db.query(KnowledgeDocument)
        .filter_by(document_id=document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    try:
        remove_document(db, document)

        return {
            "deleted": True,
            "document_id": document_id,
        }

    except Exception:
        db.rollback()
        logger.exception(
            "Document deletion failed: %s",
            document_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not delete document vectors",
        )


# --------------------------------------------------
# KNOWLEDGE SEARCH
# --------------------------------------------------

@app.post("/api/knowledge/search")
def knowledge_search(
    payload: dict,
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    query = str(payload.get("query", "")).strip()

    if len(query) < 3:
        raise HTTPException(
            status_code=422,
            detail="Query must contain at least 3 characters",
        )

    try:
        hits = [
            item
            for item in search_chunks(query)
            if item["score"] >= settings.similarity_threshold
        ]

        return {
            "results": [
                {
                    "document_name": item["document_name"],
                    "chunk_id": item["chunk_id"],
                    "score": item["score"],
                    "text": item["text"],
                }
                for item in hits
            ]
        }

    except Exception:
        logger.exception("Knowledge search failed")
        raise HTTPException(
            status_code=503,
            detail="Knowledge search unavailable; verify embedding model and Qdrant.",
        )


# --------------------------------------------------
# ESCALATED TICKETS
# --------------------------------------------------

@app.get("/api/agents/escalated")
def escalated(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent")),
):
    rows = (
        db.query(Ticket)
        .filter(Ticket.status == "Escalated")
        .order_by(Ticket.created_at.desc())
        .all()
    )

    return [ticket_out(ticket, current_user) for ticket in rows]


# --------------------------------------------------
# APPROVE AI RESPONSE
# --------------------------------------------------

@app.post("/api/agents/{ticket_id}/approve")
def approve(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent")),
):
    """
    Approve an AI-generated customer response.
    Successful approval resolves the ticket and records
    the approval action in the audit history.
    """

    ticket = get_ticket_or_404(db, ticket_id)
    result = ticket.ai_result

    if not result:
        raise HTTPException(
            status_code=409,
            detail="Run AI analysis before approving a response",
        )

    if not result.available:
        raise HTTPException(
            status_code=409,
            detail="AI analysis is unavailable; there is no response to approve",
        )

    if result.escalation_required:
        raise HTTPException(
            status_code=409,
            detail=(
                "Human review is required. "
                "This AI response cannot be approved automatically."
            ),
        )

    if not (result.customer_response or "").strip():
        raise HTTPException(
            status_code=409,
            detail="No customer response is available to approve",
        )

    if result.approval_status == "Rejected":
        raise HTTPException(
            status_code=409,
            detail="A rejected response cannot be approved",
        )

    # Idempotency: do not duplicate approval records.
    if (
        result.approval_status == "Approved"
        and ticket.status == "Resolved"
    ):
        return {
            "approval_status": result.approval_status,
            "ticket_status": ticket.status,
            "customer_response": result.customer_response,
            "ticket": ticket_out(ticket, current_user),
            "message": "Response was already approved",
        }

    old_status = ticket.status
    approved_response = result.customer_response

    try:
        result.approval_status = "Approved"
        ticket.status = "Resolved"

        db.add(
            TicketActionHistory(
                ticket_id=ticket.ticket_id,
                action="APPROVED",
                previous_response=approved_response,
                new_response=approved_response,
                reason=None,
                actor=current_user.full_name,
            )
        )

        if old_status != "Resolved":
            db.add(
                TicketHistory(
                    ticket_id=ticket.ticket_id,
                    old_status=old_status,
                    new_status="Resolved",
                    note=(
                        "AI-generated customer response "
                        "approved by support agent"
                    ),
                )
            )

        db.commit()
        db.refresh(ticket)
        db.refresh(result)

        return {
            "approval_status": result.approval_status,
            "ticket_status": ticket.status,
            "customer_response": result.customer_response,
            "ticket": ticket_out(ticket, current_user),
            "message": "Customer response approved successfully",
        }

    except Exception:
        db.rollback()
        logger.exception(
            "Approval failed for ticket %s",
            ticket_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Approval could not be saved",
        )


# --------------------------------------------------
# EDIT AI CUSTOMER RESPONSE
# --------------------------------------------------

@app.post("/api/agents/{ticket_id}/edit-response")
def edit_response(
    ticket_id: str,
    payload: EditResponse,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent")),
):
    ticket = get_ticket_or_404(db, ticket_id)

    if not ticket.ai_result:
        raise HTTPException(
            status_code=409,
            detail="Run AI analysis before editing a response",
        )

    result = ticket.ai_result

    if result.escalation_required:
        raise HTTPException(
            status_code=409,
            detail="Human review is required for this ticket",
        )

    if ticket.status == "Resolved" or result.approval_status == "Approved":
        raise HTTPException(
            status_code=409,
            detail="An approved or resolved response cannot be edited",
        )

    response_text = payload.customer_response.strip()

    if not response_text:
        raise HTTPException(
            status_code=422,
            detail="Customer response cannot be empty",
        )

    previous_response = result.customer_response

    if previous_response == response_text:
        raise HTTPException(
            status_code=422,
            detail="New response must be different from the existing response",
        )

    try:
        action_history = TicketActionHistory(
            ticket_id=ticket.ticket_id,
            action="EDITED",
            previous_response=previous_response,
            new_response=response_text,
            reason=None,
            actor=current_user.full_name,
        )

        db.add(action_history)

        result.customer_response = response_text
        result.approval_status = "Edited"

        db.commit()
        db.refresh(result)
        db.refresh(action_history)

        return {
            "approval_status": result.approval_status,
            "customer_response": result.customer_response,
            "action_history_id": action_history.id,
            "message": "Customer response updated successfully",
        }

    except Exception:
        db.rollback()
        logger.exception(
            "Response editing failed for ticket %s",
            ticket_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Customer response could not be updated",
        )


# --------------------------------------------------
# REJECT AI CUSTOMER RESPONSE
# --------------------------------------------------

@app.post("/api/agents/{ticket_id}/reject")
def reject_response(
    ticket_id: str,
    payload: RejectResponse,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent")),
):
    ticket = get_ticket_or_404(db, ticket_id)
    result = ticket.ai_result

    if not result:
        raise HTTPException(
            status_code=409,
            detail="Run AI analysis before rejecting a response",
        )

    if not result.available:
        raise HTTPException(
            status_code=409,
            detail="AI analysis is unavailable",
        )

    if result.escalation_required:
        raise HTTPException(
            status_code=409,
            detail="This ticket already requires human review",
        )

    if not (result.customer_response or "").strip():
        raise HTTPException(
            status_code=409,
            detail="No customer response is available to reject",
        )

    if ticket.status == "Resolved" or result.approval_status == "Approved":
        raise HTTPException(
            status_code=409,
            detail="An approved response cannot be rejected",
        )

    if result.approval_status == "Rejected":
        return {
            "approval_status": result.approval_status,
            "ticket_status": ticket.status,
            "message": "Response was already rejected",
        }

    reason = payload.reason.strip()

    if len(reason) < 5:
        raise HTTPException(
            status_code=422,
            detail="Rejection reason must contain at least 5 characters",
        )

    try:
        result.approval_status = "Rejected"

        db.add(
            TicketActionHistory(
                ticket_id=ticket.ticket_id,
                action="REJECTED",
                previous_response=result.customer_response,
                new_response=None,
                reason=reason,
                actor=current_user.full_name,
            )
        )

        db.add(
            AgentNote(
                ticket_id=ticket.ticket_id,
                note=f"AI response rejected. Reason: {reason}",
                author=current_user.full_name,
            )
        )

        db.commit()
        db.refresh(result)
        db.refresh(ticket)

        return {
            "approval_status": result.approval_status,
            "ticket_status": ticket.status,
            "rejection_reason": reason,
            "message": "AI response rejected successfully",
        }

    except Exception:
        db.rollback()
        logger.exception(
            "Response rejection failed for ticket %s",
            ticket_id,
        )
        raise HTTPException(
            status_code=500,
            detail="AI response could not be rejected",
        )


# --------------------------------------------------
# ADD INTERNAL NOTE
# --------------------------------------------------

@app.post("/api/agents/{ticket_id}/notes", status_code=201)
def add_note(
    ticket_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent")),
):
    ticket = get_ticket_or_404(db, ticket_id)
    note_text = payload.note.strip()

    if not note_text:
        raise HTTPException(
            status_code=422,
            detail="Note cannot be empty",
        )

    try:
        note = AgentNote(
            ticket_id=ticket.ticket_id,
            note=note_text,
            author=current_user.full_name,
        )

        db.add(note)
        db.commit()
        db.refresh(note)

        return {
            "id": note.id,
            "note": note.note,
            "author": note.author,
            "created_at": note.created_at,
        }

    except Exception:
        db.rollback()
        logger.exception("Internal note creation failed")
        raise HTTPException(
            status_code=500,
            detail="Internal note could not be saved",
        )


# --------------------------------------------------
# ANALYTICS OVERVIEW
# --------------------------------------------------

@app.get("/api/analytics/overview")
def overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    from sqlalchemy import func
    from datetime import timezone

    all_tickets = db.query(Ticket).all()
    total = len(all_tickets)

    resolution_rows = (
        db.query(
            TicketHistory.ticket_id,
            func.max(TicketHistory.created_at),
        )
        .filter(TicketHistory.new_status == "Resolved")
        .group_by(TicketHistory.ticket_id)
        .all()
    )

    latest_resolutions = {
        ticket_id: resolved_at
        for ticket_id, resolved_at in resolution_rows
    }

    durations = []

    for ticket in all_tickets:
        if ticket.status != "Resolved":
            continue

        resolution_time = latest_resolutions.get(ticket.ticket_id)

        if not resolution_time or not ticket.created_at:
            continue

        start_time = ticket.created_at
        end_time = resolution_time

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        duration = (
            end_time - start_time
        ).total_seconds() / 3600

        if duration >= 0:
            durations.append(duration)

    average_resolution = (
        round(sum(durations) / len(durations), 2)
        if durations
        else None
    )

    ai_processed = sum(
        bool(
            ticket.ai_result
            and ticket.ai_result.available
        )
        for ticket in all_tickets
    )

    ai_processed_without_escalation = sum(
        bool(
            ticket.ai_result
            and ticket.ai_result.available
            and not ticket.ai_result.escalation_required
        )
        for ticket in all_tickets
    )

    ai_escalation_required = sum(
        bool(
            ticket.ai_result
            and ticket.ai_result.escalation_required
        )
        for ticket in all_tickets
    )

    open_tickets = sum(
        ticket.status in ("Open", "In Progress", "Pending")
        for ticket in all_tickets
    )

    resolved_tickets = sum(
        ticket.status == "Resolved"
        for ticket in all_tickets
    )

    escalated_tickets = sum(
        ticket.status == "Escalated"
        for ticket in all_tickets
    )

    critical_tickets = sum(
        ticket.priority == "Critical"
        for ticket in all_tickets
    )

    recent_tickets = sorted(
        all_tickets,
        key=lambda ticket: ticket.created_at,
        reverse=True,
    )[:6]

    return {
        "total_tickets": total,
        "open_tickets": open_tickets,
        "resolved_tickets": resolved_tickets,
        "escalated_tickets": escalated_tickets,
        "critical_tickets": critical_tickets,
        "average_resolution_hours": average_resolution,
        "ai_processed": ai_processed,
        "ai_processed_without_escalation": ai_processed_without_escalation,
        "ai_escalation_required": ai_escalation_required,
        "ai_handled": ai_processed_without_escalation,
        "human_escalated": ai_escalation_required,
        "recent_tickets": [
            ticket_out(ticket, current_user)
            for ticket in recent_tickets
        ],
    }


# --------------------------------------------------
# ANALYTICS: CATEGORIES
# --------------------------------------------------

@app.get("/api/analytics/categories")
def categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    rows = (
        db.query(
            Ticket.category,
            func.count(Ticket.id),
        )
        .group_by(Ticket.category)
        .all()
    )

    return [
        {
            "name": name or "Unclassified",
            "value": count,
        }
        for name, count in rows
    ]


# --------------------------------------------------
# ANALYTICS: PRIORITIES
# --------------------------------------------------

@app.get("/api/analytics/priorities")
def priorities(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    rows = (
        db.query(
            Ticket.priority,
            func.count(Ticket.id),
        )
        .group_by(Ticket.priority)
        .all()
    )

    return [
        {
            "name": name,
            "value": count,
        }
        for name, count in rows
    ]


# --------------------------------------------------
# ANALYTICS: TRENDS
# --------------------------------------------------

@app.get("/api/analytics/trends")
def ticket_trends(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=days - 1)
    end_day = today + timedelta(days=1)

    start_datetime = datetime(
        start_day.year,
        start_day.month,
        start_day.day,
        tzinfo=timezone.utc,
    )

    end_datetime = datetime(
        end_day.year,
        end_day.month,
        end_day.day,
        tzinfo=timezone.utc,
    )

    trend_data = {}

    for i in range(days):
        current_day = start_day + timedelta(days=i)
        date_key = current_day.isoformat()

        trend_data[date_key] = {
            "date": date_key,
            "created": 0,
            "resolved": 0,
        }

    created_tickets = (
        db.query(Ticket.created_at)
        .filter(
            Ticket.created_at >= start_datetime,
            Ticket.created_at < end_datetime,
        )
        .all()
    )

    for (created_at,) in created_tickets:
        created_date = created_at.date().isoformat()

        if created_date in trend_data:
            trend_data[created_date]["created"] += 1

    resolution_events = (
        db.query(TicketHistory.created_at)
        .filter(
            TicketHistory.new_status == "Resolved",
            TicketHistory.created_at >= start_datetime,
            TicketHistory.created_at < end_datetime,
        )
        .all()
    )

    for (resolved_at,) in resolution_events:
        resolved_date = resolved_at.date().isoformat()

        if resolved_date in trend_data:
            trend_data[resolved_date]["resolved"] += 1

    return list(trend_data.values())


# --------------------------------------------------
# ANALYTICS: SLA
# --------------------------------------------------

@app.get("/api/analytics/sla")
def sla_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    from datetime import datetime, timezone
    from sqlalchemy import func

    SLA_TARGETS = {
        "Critical": 4,
        "High": 12,
        "Medium": 24,
        "Low": 48,
    }

    def normalize_datetime(value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    current_time = datetime.now(timezone.utc)
    all_tickets = db.query(Ticket).all()

    resolution_rows = (
        db.query(
            TicketHistory.ticket_id,
            func.max(TicketHistory.created_at),
        )
        .filter(TicketHistory.new_status == "Resolved")
        .group_by(TicketHistory.ticket_id)
        .all()
    )

    latest_resolutions = {
        ticket_id: resolved_at
        for ticket_id, resolved_at in resolution_rows
    }

    within_sla = 0
    breached = 0
    unknown = 0
    ticket_results = []

    for ticket in all_tickets:
        target_hours = SLA_TARGETS.get(ticket.priority)

        if target_hours is None or ticket.created_at is None:
            unknown += 1
            continue

        start_time = normalize_datetime(ticket.created_at)

        if ticket.status == "Resolved":
            resolved_at = latest_resolutions.get(ticket.ticket_id)

            if resolved_at is None:
                unknown += 1
                continue

            end_time = normalize_datetime(resolved_at)

        else:
            end_time = current_time

        elapsed_hours = (
            end_time - start_time
        ).total_seconds() / 3600

        if elapsed_hours < 0:
            unknown += 1
            continue

        remaining_hours = target_hours - elapsed_hours

        if remaining_hours > 0:
            sla_status = "Within SLA"
            within_sla += 1
        else:
            sla_status = "Breached"
            breached += 1

        ticket_results.append({
            "ticket_id": ticket.ticket_id,
            "subject": ticket.subject,
            "priority": ticket.priority,
            "status": ticket.status,
            "sla_target_hours": target_hours,
            "elapsed_hours": round(elapsed_hours, 2),
            "remaining_hours": round(remaining_hours, 2),
            "sla_status": sla_status,
        })

    evaluated = within_sla + breached

    compliance_percentage = (
        round((within_sla / evaluated) * 100, 2)
        if evaluated
        else None
    )

    return {
        "total_tickets": len(all_tickets),
        "evaluated_tickets": evaluated,
        "within_sla": within_sla,
        "breached": breached,
        "unknown": unknown,
        "compliance_percentage": compliance_percentage,
        "sla_targets": SLA_TARGETS,
        "tickets": ticket_results,
    }


# --------------------------------------------------
# ANALYTICS: APPROVALS
# --------------------------------------------------

@app.get("/api/analytics/approvals")
def approval_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    from sqlalchemy import func

    status_rows = (
        db.query(
            TicketAIResult.approval_status,
            func.count(TicketAIResult.id),
        )
        .filter(TicketAIResult.available.is_(True))
        .group_by(TicketAIResult.approval_status)
        .all()
    )

    status_counts = {
        "Approved": 0,
        "Rejected": 0,
        "Edited": 0,
        "Pending": 0,
    }

    for status, count in status_rows:
        if status in status_counts:
            status_counts[status] = count

    action_rows = (
        db.query(
            TicketActionHistory.action,
            func.count(TicketActionHistory.id),
        )
        .group_by(TicketActionHistory.action)
        .all()
    )

    action_counts = {
        "APPROVED": 0,
        "REJECTED": 0,
        "EDITED": 0,
    }

    for action, count in action_rows:
        if action in action_counts:
            action_counts[action] = count

    total_responses = sum(status_counts.values())

    approval_rate = (
        round(status_counts["Approved"] / total_responses * 100, 2)
        if total_responses
        else 0
    )

    rejection_rate = (
        round(status_counts["Rejected"] / total_responses * 100, 2)
        if total_responses
        else 0
    )

    return {
        "total_responses": total_responses,
        "status_distribution": status_counts,
        "approval_rate": approval_rate,
        "rejection_rate": rejection_rate,
        "total_actions": sum(action_counts.values()),
        "action_distribution": action_counts,
    }


# --------------------------------------------------
# ANALYTICS: SUPPORT ACTIVITY
# --------------------------------------------------

@app.get("/api/analytics/support-activity")
def support_activity_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Agent", "Viewer")),
):
    action_rows = (
        db.query(
            TicketActionHistory.actor,
            TicketActionHistory.action,
            func.count(TicketActionHistory.id),
        )
        .group_by(
            TicketActionHistory.actor,
            TicketActionHistory.action,
        )
        .all()
    )

    actions_by_actor = {}

    action_distribution = {
        "APPROVED": 0,
        "REJECTED": 0,
        "EDITED": 0,
    }

    for actor, action, count in action_rows:
        actor_name = actor or "Unknown"

        if actor_name not in actions_by_actor:
            actions_by_actor[actor_name] = {
                "APPROVED": 0,
                "REJECTED": 0,
                "EDITED": 0,
                "total_actions": 0,
            }

        if action in action_distribution:
            action_distribution[action] += count
            actions_by_actor[actor_name][action] += count
            actions_by_actor[actor_name]["total_actions"] += count

    note_rows = (
        db.query(
            AgentNote.author,
            func.count(AgentNote.id),
        )
        .group_by(AgentNote.author)
        .all()
    )

    notes_by_author = {
        author or "Unknown": count
        for author, count in note_rows
    }

    total_actions = sum(action_distribution.values())
    total_notes = sum(notes_by_author.values())

    resolved_tickets = (
        db.query(Ticket)
        .filter(Ticket.status == "Resolved")
        .count()
    )

    escalated_tickets = (
        db.query(Ticket)
        .filter(Ticket.status == "Escalated")
        .count()
    )

    return {
        "total_support_actions": total_actions,
        "action_distribution": action_distribution,
        "actions_by_actor": actions_by_actor,
        "total_internal_notes": total_notes,
        "notes_by_author": notes_by_author,
        "total_resolved_tickets": resolved_tickets,
        "total_escalated_tickets": escalated_tickets,
        "individual_agent_performance_available": False,
        "limitation": (
            "Individual agent performance requires authenticated "
            "agent identities."
        ),
    }


# --------------------------------------------------
# AUTHENTICATION - LOGIN
# --------------------------------------------------

@app.post("/api/auth/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(credentials.email).strip().lower()

    user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )

    if not user or not verify_password(
        credentials.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account is inactive. Contact an administrator.",
        )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


# --------------------------------------------------
# USER MANAGEMENT - CREATE USER
# --------------------------------------------------

@app.post(
    "/api/users",
    response_model=UserResponse,
    status_code=201,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    email = str(payload.email).strip().lower()

    # Check duplicate email
    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists.",
        )

    # Create new user
    new_user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create user.",
        )

    return new_user


# --------------------------------------------------
# USER MANAGEMENT - LIST USERS
# --------------------------------------------------

@app.get(
    "/api/users",
    response_model=list[UserResponse],
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    users = (
        db.query(User)
        .order_by(User.id.asc())
        .all()
    )

    return users


# --------------------------------------------------
# USER MANAGEMENT - UPDATE USER ROLE
# --------------------------------------------------

@app.patch(
    "/api/users/{user_id}/role",
    response_model=UserResponse,
)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    # Prevent Admin from changing their own role
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own role.",
        )

    target_user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    # Protect existing Admin accounts
    if target_user.role == "Admin":
        raise HTTPException(
            status_code=403,
            detail="Admin role cannot be changed.",
        )

    target_user.role = payload.role

    try:
        db.commit()
        db.refresh(target_user)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to update user role.",
        )

    return target_user

# --------------------------------------------------
# USER MANAGEMENT - UPDATE ACCOUNT STATUS
# --------------------------------------------------

@app.patch(
    "/api/users/{user_id}/status",
    response_model=UserResponse,
)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    # Prevent Admin from deactivating their own account
    if user_id == current_user.id and not payload.is_active:
        raise HTTPException(
            status_code=400,
            detail="You cannot deactivate your own account.",
        )

    target_user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    # Protect Admin accounts
    if target_user.role == "Admin" and not payload.is_active:
        raise HTTPException(
            status_code=403,
            detail="Admin accounts cannot be deactivated.",
        )

    target_user.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(target_user)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to update user status.",
        )

    return target_user