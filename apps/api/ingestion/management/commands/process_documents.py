from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ingestion.worker import run_forever, run_once


class Command(BaseCommand):
    help = "Process pending documents: extract text, chunk, embed and store."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process the queue and exit.")
        parser.add_argument(
            "--interval", type=float, default=5.0, help="Seconds to wait when the queue is empty."
        )

    def handle(self, *args, once, interval, **options):
        if settings.EMBEDDING_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not set.")

        if once:
            processed = run_once()
            self.stdout.write(f"Processed {processed} document(s).")
        else:
            self.stdout.write("Worker started. Press Ctrl+C to stop.")
            run_forever(interval)
