
import hashlib
import logging
import re
from pathlib import Path

import fitz
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument
from app.rag.chunking import chunk_text
from app.services.vector_store import (
    upsert_chunks,
    delete_document_vectors,
)


logger = logging.getLogger("resolveai")

ALLOWED = {".pdf", ".txt", ".md"}


def extract_text(filename: str, content: bytes) -> str:
    """Extract text from supported PDF, TXT and Markdown files."""

    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED:
        raise ValueError("Only PDF, TXT and MD files are supported")

    if not content:
        raise ValueError("Uploaded file is empty")

    if ext == ".pdf":
        if b"%PDF-" not in content[:1024]:
            raise ValueError("Invalid PDF file signature")

        try:
            with fitz.open(stream=content, filetype="pdf") as doc:
                if doc.is_encrypted:
                    raise ValueError(
                        "Encrypted PDF files are not supported"
                    )

                return "\n".join(
                    page.get_text() for page in doc
                )

        except ValueError:
            raise

        except Exception as error:
            raise ValueError(
                "Invalid or malformed PDF document"
            ) from error

    try:
        return content.decode("utf-8-sig")

    except UnicodeDecodeError as error:
        raise ValueError(
            "Text file must use valid UTF-8 encoding"
        ) from error


def ingest_document(
    db: Session,
    filename: str,
    content: bytes,
):
    digest = hashlib.sha256(content).hexdigest()

    existing = (
        db.query(KnowledgeDocument)
        .filter_by(content_hash=digest)
        .first()
    )

    if existing:
        return existing, False

    text = extract_text(filename, content)

    if len(text.strip()) < 30:
        raise ValueError(
            "Document contains insufficient extractable text"
        )

    safe_name = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        Path(filename).name,
    )[:255]

    doc = KnowledgeDocument(
        filename=safe_name,
        content_hash=digest,
        status="Processing",
    )

    db.add(doc)
    db.flush()

    chunks = chunk_text(text)

    # Compensating cleanup: upsert may partially succeed.
    vectors_may_exist = False

    try:
        vectors_may_exist = True

        upsert_chunks(
            doc.document_id,
            safe_name,
            chunks,
        )

        doc.chunk_count = len(chunks)
        doc.status = "Indexed"

        db.commit()
        db.refresh(doc)

        return doc, True

    except Exception:
        db.rollback()

        if vectors_may_exist:
            try:
                delete_document_vectors(doc.document_id)

            except Exception:
                logger.exception(
                    "Qdrant cleanup failed for document ID: %s",
                    doc.document_id,
                )

        raise


def remove_document(db: Session, doc: KnowledgeDocument):
    delete_document_vectors(doc.document_id)
    db.delete(doc)
    db.commit()
