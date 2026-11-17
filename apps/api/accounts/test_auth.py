import pytest

from accounts.models import User
from organizations.models import Membership

pytestmark = pytest.mark.django_db

REGISTER = "/api/auth/register/"
TOKEN = "/api/auth/token/"
ME = "/api/auth/me/"


@pytest.fixture
def register_payload(password):
    return {
        "email": "Alice@Example.com",
        "password": password,
        "full_name": "Alice Doe",
        "organization_name": "Acme Inc",
    }


def test_register_creates_user_organization_and_owner_membership(api_client, register_payload):
    response = api_client.post(REGISTER, register_payload, format="json")

    assert response.status_code == 201
    user = User.objects.get(email="alice@example.com")
    membership = Membership.objects.get(user=user)
    assert membership.role == Membership.Role.OWNER
    assert membership.organization.name == "Acme Inc"


def test_register_rejects_duplicate_email_ignoring_case(api_client, register_payload):
    api_client.post(REGISTER, register_payload, format="json")

    other = {**register_payload, "email": "ALICE@example.com"}
    response = api_client.post(REGISTER, other, format="json")

    assert response.status_code == 400
    assert "email" in response.json()


def test_register_rejects_weak_password(api_client, register_payload):
    response = api_client.post(
        REGISTER, {**register_payload, "password": "12345678"}, format="json"
    )

    assert response.status_code == 400
    assert "password" in response.json()


def test_login_then_me_returns_profile_and_memberships(api_client, register_payload, password):
    api_client.post(REGISTER, register_payload, format="json")

    login = api_client.post(
        TOKEN, {"email": "alice@example.com", "password": password}, format="json"
    )
    assert login.status_code == 200

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
    response = api_client.get(ME)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["memberships"][0]["role"] == "owner"
    assert body["memberships"][0]["organization"]["name"] == "Acme Inc"


def test_login_with_wrong_password_is_rejected(api_client, register_payload):
    api_client.post(REGISTER, register_payload, format="json")

    response = api_client.post(
        TOKEN, {"email": "alice@example.com", "password": "wrong-password"}, format="json"
    )

    assert response.status_code == 401


def test_me_requires_authentication(api_client):
    assert api_client.get(ME).status_code == 401


def test_login_is_throttled_after_repeated_failures(api_client):
    bad = {"email": "nobody@example.com", "password": "wrong-password"}

    for _ in range(10):
        assert api_client.post(TOKEN, bad, format="json").status_code == 401

    assert api_client.post(TOKEN, bad, format="json").status_code == 429
