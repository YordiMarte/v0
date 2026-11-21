import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from documents.models import Document
from ingestion.chunking import split_text
from ingestion.embeddings import embed_texts, model_id
from ingestion.errors import IngestionError
from ingestion.extraction import extract_text
from ingestion.models import Chunk

logger = logging.getLogger(__name__)


def _read_file(document: Document) -> bytes:
    try:
        with document.file.open("rb") as handle:
            return handle.read()
    except FileNotFoundError as exc:
        raise IngestionError("The stored file could not be found.") from exc


def _embed_all(chunks: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    size = settings.INGEST_BATCH_SIZE
    for start in range(0, len(chunks), size):
        vectors.extend(embed_texts(chunks[start : start + size]))
    if len(vectors) != len(chunks):
        raise IngestionError("The embedding service returned an unexpected response.")
    return vectors


def _store(document: Document, chunks: list[str], vectors: list[list[float]]) -> None:
    with transaction.atomic():
        # Lock the row so a concurrent delete cannot slip in between the checks.
        locked = Document.objects.select_for_update().filter(pk=document.pk).first()
        if locked is None:
            return  # deleted while it was being processed

        # Replace, never append: reprocessing must not duplicate chunks.
        Chunk.objects.filter(document=locked).delete()
        Chunk.objects.bulk_create(
            [
                Chunk(
                    document=locked,
                    organization_id=locked.organization_id,
                    position=position,
                    content=content,
                    embedding=vector,
                    embedding_model=model_id(),
                )
                for position, (content, vector) in enumerate(zip(chunks, vectors, strict=True))
            ],
            batch_size=200,
        )
        locked.status = Document.Status.READY
        locked.error_message = ""
        locked.save(update_fields=["status", "error_message", "updated_at"])


def _fail(document: Document, message: str) -> None:
    # update() is a no-op if the document was deleted in the meantime.
    Document.objects.filter(pk=document.pk).update(
        status=Document.Status.FAILED,
        error_message=message[:500],
        updated_at=timezone.now(),
    )


def process_document(document: Document) -> None:
    """Extract, chunk, embed and store one document.

    Expected problems (unreadable file, no text, service down) end as a
    "failed" document with a message the user can read. Anything unexpected is
    logged in full and shown to the user as a generic message.
    """
    try:
        text = extract_text(_read_file(document), document.content_type)
        chunks = split_text(
            text, size=settings.INGEST_CHUNK_SIZE, overlap=settings.INGEST_CHUNK_OVERLAP
        )
        if not chunks:
            raise IngestionError(
                "No text could be extracted. Scanned documents are not supported yet."
            )
        if len(chunks) > settings.INGEST_MAX_CHUNKS:
            raise IngestionError("The document is too long to process.")

        # The slow external calls happen outside any database transaction.
        vectors = _embed_all(chunks)
        _store(document, chunks, vectors)
    except IngestionError as exc:
        _fail(document, str(exc))
    except Exception:
        logger.exception("Unexpected error processing document %s", document.id)
        _fail(document, "Processing failed unexpectedly. Please try again later.")
