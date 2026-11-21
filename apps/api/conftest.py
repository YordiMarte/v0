import itertools

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import User
from documents.services import create_document
from ingestion.models import EMBEDDING_DIMENSIONS
from organizations.models import Membership, Organization


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the cache; start every test from zero."""
    cache.clear()


@pytest.fixture(autouse=True)
def _in_memory_storage(settings):
    """Tests never touch the disk or S3."""
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def password() -> str:
    return "Tr0ub4dor&3-horse"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def auth_client():
    def _make(user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _make


@pytest.fixture
def make_member(db, password):
    def _make(email: str, organization: Organization, role=Membership.Role.MEMBER) -> User:
        user = User.objects.create_user(
            email=email, password=password, full_name=email.split("@")[0]
        )
        Membership.objects.create(user=user, organization=organization, role=role)
        return user

    return _make


@pytest.fixture
def org_a(db) -> Organization:
    return Organization.objects.create(name="Org A")


@pytest.fixture
def org_b(db) -> Organization:
    return Organization.objects.create(name="Org B")


@pytest.fixture
def alice(make_member, org_a) -> User:
    return make_member("alice@example.com", org_a, Membership.Role.OWNER)


@pytest.fixture
def bob(make_member, org_b) -> User:
    return make_member("bob@example.com", org_b, Membership.Role.OWNER)


@pytest.fixture
def make_document(db):
    counter = itertools.count()

    def _make(organization, uploaded_by=None, name="doc.txt", content=None):
        content = content or f"content {next(counter)}".encode()
        return create_document(
            organization=organization,
            uploaded_by=uploaded_by,
            upload=SimpleUploadedFile(name, content),
        )

    return _make


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Replace the OpenAI call. Returns the list of batches that were requested."""
    batches: list[list[str]] = []

    def fake(texts):
        batches.append(list(texts))
        # Never a zero vector: cosine distance is undefined for them.
        return [[1.0, float(len(text))] + [0.0] * (EMBEDDING_DIMENSIONS - 2) for text in texts]

    monkeypatch.setattr("ingestion.pipeline.embed_texts", fake)
    return batches


def _build_pdf(text: str) -> bytes:
    """A minimal valid one-page PDF containing `text` (no parentheses)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return bytes(out)


@pytest.fixture
def make_pdf():
    return _build_pdf
