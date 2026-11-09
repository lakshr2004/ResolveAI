import pytest
import uuid
from unittest.mock import patch

from app.database import SessionLocal
from app.services.document_service import ingest_document, remove_document
from app.models import KnowledgeDocument


def unique_content(text: str) -> bytes:
    """Generate unique document content for every test execution."""
    marker = uuid.uuid4().hex
    return f"# Support guide\n\n{text}\n\nTest reference: {marker}".encode("utf-8")


def test_markdown_ingestion_and_vector_deletion():
    content = unique_content(
        "Customers should use the account settings page to download "
        "completed invoices. Contact support if the invoice is missing."
    )

    with SessionLocal() as db:
        doc_id = None

        try:
            with patch("app.services.document_service.upsert_chunks") as upsert:
                doc, created = ingest_document(
                    db, "invoice_guide.md", content
                )

                assert created is True
                assert doc.status == "Indexed"
                assert doc.chunk_count >= 1

                upsert.assert_called_once()
                doc_id = doc.document_id

            with patch(
                "app.services.document_service.delete_document_vectors"
            ) as delete:
                remove_document(db, doc)

                delete.assert_called_once_with(doc_id)

            assert (
                db.query(KnowledgeDocument)
                .filter_by(document_id=doc_id)
                .first()
                is None
            )

        finally:
            if doc_id:
                remaining = (
                    db.query(KnowledgeDocument)
                    .filter_by(document_id=doc_id)
                    .first()
                )
                if remaining:
                    db.delete(remaining)
                    db.commit()


def test_duplicate_document_is_not_reingested():
    content = unique_content(
        "This is a sufficiently long support guide with instructions "
        "for a customer account and billing history."
    )

    with SessionLocal() as db:
        first = None

        try:
            with patch("app.services.document_service.upsert_chunks") as upsert:
                first, created = ingest_document(
                    db, "guide.md", content
                )

                second, created_again = ingest_document(
                    db, "copy.md", content
                )

                assert created is True
                assert created_again is False

                assert first.document_id == second.document_id

                assert first.filename == "guide.md"
                assert first.status == "Indexed"

                upsert.assert_called_once()

        finally:
            if first:
                remaining = (
                    db.query(KnowledgeDocument)
                    .filter_by(document_id=first.document_id)
                    .first()
                )
                if remaining:
                    db.delete(remaining)
                    db.commit()



import pytest
from app.services.document_service import extract_text


def test_reject_malformed_pdf():
    with pytest.raises(ValueError):
        extract_text(
            "malformed.pdf",
            b"This is not a valid PDF document.",
        )


def test_reject_invalid_utf8_text():
    with pytest.raises(ValueError):
        extract_text(
            "invalid.txt",
            b"\xff\xfe\xfa\xff",
        )



def test_vector_upsert_failure_rolls_back_document():
    content = unique_content(
        "This support guide contains enough information "
        "to test vector insertion failure and rollback."
    )

    with SessionLocal() as db:
        with patch(
            "app.services.document_service.upsert_chunks",
            side_effect=RuntimeError("Qdrant insertion failed"),
        ), patch(
            "app.services.document_service.delete_document_vectors"
        ) as delete_vectors:

            with pytest.raises(RuntimeError):
                ingest_document(db, "failure_test.md", content)

            delete_vectors.assert_called_once()

            failed_document_id = delete_vectors.call_args.args[0]

            remaining = db.query(KnowledgeDocument).filter_by(
                document_id=failed_document_id
            ).first()

            assert remaining is None


def test_database_commit_failure_cleans_up_vectors():
    content = unique_content(
        "This support guide contains enough information "
        "to test database commit failure and vector cleanup."
    )

    with SessionLocal() as db:
        with patch(
            "app.services.document_service.upsert_chunks"
        ) as upsert, patch(
            "app.services.document_service.delete_document_vectors"
        ) as delete_vectors, patch.object(
            db,
            "commit",
            side_effect=RuntimeError("Database commit failed"),
        ):

            with pytest.raises(RuntimeError):
                ingest_document(db, "commit_failure.md", content)

            upsert.assert_called_once()
            delete_vectors.assert_called_once()

            failed_document_id = delete_vectors.call_args.args[0]

            remaining = db.query(KnowledgeDocument).filter_by(
                document_id=failed_document_id
            ).first()

            assert remaining is None
