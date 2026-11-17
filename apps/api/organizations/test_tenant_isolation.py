import pytest

from organizations.models import Membership

pytestmark = pytest.mark.django_db


def test_user_only_lists_own_organizations(auth_client, alice, org_a, org_b, bob):
    response = auth_client(alice).get("/api/organizations/")

    assert response.status_code == 200
    assert [org["id"] for org in response.json()] == [str(org_a.id)]


def test_user_cannot_retrieve_another_organization(auth_client, alice, org_b):
    response = auth_client(alice).get(f"/api/organizations/{org_b.id}/")

    assert response.status_code == 404


def test_user_cannot_list_members_of_another_organization(auth_client, alice, org_b, bob):
    response = auth_client(alice).get(f"/api/organizations/{org_b.id}/members/")

    assert response.status_code == 404


def test_member_sees_members_of_own_organization(auth_client, alice, org_a, make_member):
    make_member("carol@example.com", org_a, Membership.Role.MEMBER)

    response = auth_client(alice).get(f"/api/organizations/{org_a.id}/members/")

    assert response.status_code == 200
    assert {m["email"] for m in response.json()} == {"alice@example.com", "carol@example.com"}


def test_malformed_organization_id_returns_404(auth_client, alice):
    assert auth_client(alice).get("/api/organizations/not-a-uuid/").status_code == 404


def test_anonymous_requests_are_rejected(api_client, org_a):
    assert api_client.get("/api/organizations/").status_code == 401
    assert api_client.get(f"/api/organizations/{org_a.id}/members/").status_code == 401
