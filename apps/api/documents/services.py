import hashlib
import uuid

from django.db import IntegrityError, transaction

from documents.models import Document
from documents.validators import ALLOWED_EXTENSIONS, clean_filename, extension_of
from organizations.models import Organization


class DuplicateDocument(Exception):
    """The organization already has a document with identical content."""

    def __init__(self, document_id: uuid.UUID):
        super().__init__(str(document_id))
        self.document_id = document_id


def _sha256_of(upload) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def create_document(*, organization: Organization, uploaded_by, upload) -> Document:
    """Store an already validated upload and register it for processing."""
    original_name = clean_filename(upload.name)
    digest = _sha256_of(upload)

    existing = Document.objects.filter(organization=organization, sha256=digest).first()
    if existing is not None:
        raise DuplicateDocument(existing.id)

    document = Document(
        organization=organization,
        uploaded_by=uploaded_by,
        original_name=original_name,
        content_type=ALLOWED_EXTENSIONS[extension_of(original_name)],
        size_bytes=upload.size,
        sha256=digest,
    )

    document.file.save(upload.name, upload, save=False)
    stored_name = document.file.name
    storage = document.file.storage

    try:
        with transaction.atomic():
            document.save()
    except IntegrityError:
        # Two identical uploads raced: the unique constraint is the real guard.
        storage.delete(stored_name)
        existing = Document.objects.filter(organization=organization, sha256=digest).first()
        if existing is None:
            raise
        raise DuplicateDocument(existing.id) from None
    except Exception:
        # Never leave an orphan file behind when the database write fails.
        storage.delete(stored_name)
        raise

    return document
