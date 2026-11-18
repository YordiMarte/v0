import itertools

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import User
from documents.services import create_document
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
