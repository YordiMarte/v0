import logging
import signal
import threading
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from documents.models import Document
from ingestion.pipeline import process_document

logger = logging.getLogger(__name__)


def recover_stale() -> int:
    """Queue again the documents a dead worker left in "processing"."""
    cutoff = timezone.now() - timedelta(minutes=settings.INGEST_STALE_MINUTES)
    recovered = Document.objects.filter(
        status=Document.Status.PROCESSING, updated_at__lt=cutoff
    ).update(status=Document.Status.PENDING)
    if recovered:
        logger.warning("Re-queued %s stale document(s)", recovered)
    return recovered


def claim_next_document() -> Document | None:
    """Atomically take the oldest pending document.

    SKIP LOCKED lets several workers run side by side without ever claiming
    the same document, and without waiting on each other.
    """
    with transaction.atomic():
        document = (
            Document.objects.select_for_update(skip_locked=True)
            .filter(status=Document.Status.PENDING)
            .order_by("created_at")
            .first()
        )
        if document is None:
            return None
        document.status = Document.Status.PROCESSING
        document.save(update_fields=["status", "updated_at"])
        return document


def run_once(stop: threading.Event | None = None) -> int:
    """Process the queue until it is empty. Returns how many documents ran."""
    if stop is None:
        stop = threading.Event()

    recover_stale()
    processed = 0
    while not stop.is_set():
        document = claim_next_document()
        if document is None:
            break
        logger.info("Processing document %s", document.id)
        process_document(document)
        processed += 1
    return processed


def run_forever(interval: float) -> None:
    stop = threading.Event()

    def _request_stop(signum, _frame):
        logger.info("Signal %s received: finishing the current document, then stopping.", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    while not stop.is_set():
        if run_once(stop) == 0:
            stop.wait(interval)
