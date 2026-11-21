from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from documents.models import Document
from ingestion.errors import IngestionError
from ingestion.models import EMBEDDING_DIMENSIONS, Chunk
from ingestion.pipeline import process_document
from ingestion.worker import claim_next_document, recover_stale, run_once

pytestmark = pytest.mark.django_db

LONG_TEXT = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(12))


def test_processing_a_text_document_stores_embedded_chunks(
    org_a, alice, make_document, fake_embeddings
):
    document = make_document(org_a, alice, content=LONG_TEXT.encode())

    process_document(document)

    document.refresh_from_db()
    assert document.status == Document.Status.READY
    chunks = list(Chunk.objects.filter(document=document))
    assert len(chunks) > 1
    assert [chunk.position for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.organization_id == org_a.id for chunk in chunks)
    assert len(chunks[0].embedding) == EMBEDDING_DIMENSIONS


def test_pdf_documents_are_processed(org_a, make_document, make_pdf, fake_embeddings):
    document = make_document(org_a, name="guide.pdf", content=make_pdf("Kivoff builds software"))

    process_document(document)

    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert "Kivoff builds software" in Chunk.objects.get(document=document).content


def test_embeddings_are_requested_in_batches(org_a, make_document, fake_embeddings, settings):
    settings.INGEST_BATCH_SIZE = 2
    document = make_document(org_a, content=LONG_TEXT.encode())

    process_document(document)

    total = Chunk.objects.filter(document=document).count()
    assert len(fake_embeddings) > 1
    assert all(len(batch) <= 2 for batch in fake_embeddings)
    assert sum(len(batch) for batch in fake_embeddings) == total


def test_document_without_text_fails_with_a_clear_message(org_a, make_document, fake_embeddings):
    document = make_document(org_a, content=b"   \n\n  ")

    process_document(document)

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert "text" in document.error_message.lower()
    assert Chunk.objects.count() == 0
    assert fake_embeddings == []


def test_document_that_is_too_long_fails(org_a, make_document, fake_embeddings, settings):
    settings.INGEST_MAX_CHUNKS = 2
    document = make_document(org_a, content=LONG_TEXT.encode())

    process_document(document)

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert "too long" in document.error_message
    assert fake_embeddings == []


def test_embedding_service_failure_fails_the_document_and_stores_nothing(
    org_a, make_document, monkeypatch
):
    def broken(_texts):
        raise IngestionError("The embedding service is unavailable or over quota.")

    monkeypatch.setattr("ingestion.pipeline.embed_texts", broken)
    document = make_document(org_a, content=LONG_TEXT.encode())

    process_document(document)

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert "unavailable" in document.error_message
    assert Chunk.objects.count() == 0


def test_unexpected_errors_do_not_leak_internal_details(org_a, make_document, monkeypatch):
    def broken(_texts):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("ingestion.pipeline.embed_texts", broken)
    document = make_document(org_a, content=LONG_TEXT.encode())

    process_document(document)

    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert "secret" not in document.error_message


def test_reprocessing_replaces_chunks_instead_of_duplicating_them(
    org_a, make_document, fake_embeddings
):
    document = make_document(org_a, content=LONG_TEXT.encode())
    process_document(document)
    first_count = Chunk.objects.filter(document=document).count()

    Document.objects.filter(pk=document.pk).update(status=Document.Status.PENDING)
    document.refresh_from_db()
    process_document(document)

    assert Chunk.objects.filter(document=document).count() == first_count


def test_deleting_a_document_deletes_its_chunks(org_a, make_document, fake_embeddings):
    document = make_document(org_a, content=LONG_TEXT.encode())
    process_document(document)

    document.delete()

    assert Chunk.objects.count() == 0


# --- Queue -------------------------------------------------------------------


def test_claim_takes_the_oldest_pending_document_and_marks_it_processing(org_a, make_document):
    first = make_document(org_a)
    second = make_document(org_a)

    claimed = claim_next_document()

    assert claimed.pk == first.pk
    assert claimed.status == Document.Status.PROCESSING
    assert claim_next_document().pk == second.pk
    assert claim_next_document() is None


def test_stale_processing_documents_are_queued_again(org_a, make_document, settings):
    stale = make_document(org_a)
    fresh = make_document(org_a)
    too_old = timezone.now() - timedelta(minutes=settings.INGEST_STALE_MINUTES + 1)
    Document.objects.filter(pk=stale.pk).update(
        status=Document.Status.PROCESSING, updated_at=too_old
    )
    Document.objects.filter(pk=fresh.pk).update(status=Document.Status.PROCESSING)

    assert recover_stale() == 1

    stale.refresh_from_db()
    fresh.refresh_from_db()
    assert stale.status == Document.Status.PENDING
    assert fresh.status == Document.Status.PROCESSING


def test_run_once_processes_the_whole_queue(org_a, make_document, fake_embeddings):
    documents = [
        make_document(org_a, content=(LONG_TEXT + f"\nDocument {index}").encode())
        for index in range(2)
    ]
    documents.append(make_document(org_a, content=b"A different short document."))

    assert run_once() == 3

    assert set(Document.objects.values_list("status", flat=True)) == {Document.Status.READY}


def test_worker_command_processes_the_queue(org_a, make_document, fake_embeddings, settings):
    settings.OPENAI_API_KEY = "test-key"
    document = make_document(org_a, content=LONG_TEXT.encode())

    call_command("process_documents", "--once")

    document.refresh_from_db()
    assert document.status == Document.Status.READY


def test_worker_command_refuses_to_start_without_an_api_key(settings):
    settings.EMBEDDING_PROVIDER = "openai"
    settings.OPENAI_API_KEY = ""

    with pytest.raises(CommandError):
        call_command("process_documents", "--once")


def test_chunks_record_which_model_embedded_them(org_a, make_document, fake_embeddings, settings):
    settings.EMBEDDING_PROVIDER = "local"
    settings.EMBEDDING_MODEL = "test-model"
    document = make_document(org_a, content=LONG_TEXT.encode())

    process_document(document)

    models_used = set(Chunk.objects.values_list("embedding_model", flat=True))
    assert models_used == {"local:test-model"}
