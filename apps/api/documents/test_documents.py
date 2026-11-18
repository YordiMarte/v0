import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from documents.models import Document
from organizations.models import Membership

pytestmark = pytest.mark.django_db

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def list_url(org) -> str:
    return f"/api/organizations/{org.id}/documents/"


def detail_url(org, document) -> str:
    return f"{list_url(org)}{document.id}/"


def upload(client, org, name="report.pdf", content=PDF_BYTES):
    return client.post(
        list_url(org), {"file": SimpleUploadedFile(name, content)}, format="multipart"
    )


# --- Uploading ---------------------------------------------------------------


def test_upload_pdf_registers_a_pending_document(auth_client, alice, org_a):
    response = upload(auth_client(alice), org_a)

    assert response.status_code == 201
    body = response.json()
    assert body["original_name"] == "report.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF_BYTES)
    assert body["status"] == "pending"
    assert body["uploaded_by"] == "alice@example.com"
    assert Document.objects.get().organization == org_a


def test_response_does_not_leak_the_storage_path(auth_client, alice, org_a):
    response = upload(auth_client(alice), org_a)

    assert "file" not in response.json()
    assert "orgs/" not in response.content.decode()


@pytest.mark.parametrize("name", ["notes.txt", "readme.md"])
def test_upload_text_formats(auth_client, alice, org_a, name):
    assert upload(auth_client(alice), org_a, name, b"# hello").status_code == 201


def test_member_can_upload(auth_client, org_a, make_member):
    carol = make_member("carol@example.com", org_a, Membership.Role.MEMBER)

    assert upload(auth_client(carol), org_a).status_code == 201


def test_stored_under_opaque_name_and_original_name_is_sanitized(auth_client, alice, org_a):
    response = upload(auth_client(alice), org_a, "../../etc/passwd.txt", b"hello")

    assert response.status_code == 201
    document = Document.objects.get()
    assert document.original_name == "passwd.txt"
    assert document.file.name == f"orgs/{org_a.id}/documents/{document.id}.txt"


# --- Validation --------------------------------------------------------------


def test_rejects_unsupported_extension(auth_client, alice, org_a):
    response = upload(auth_client(alice), org_a, "run.exe", b"MZ\x90\x00")

    assert response.status_code == 400
    assert "file" in response.json()


def test_rejects_file_whose_content_does_not_match_its_extension(auth_client, alice, org_a):
    response = upload(auth_client(alice), org_a, "evil.pdf", b"#!/bin/sh\nrm -rf /")

    assert response.status_code == 400


def test_rejects_binary_content_disguised_as_text(auth_client, alice, org_a):
    response = upload(auth_client(alice), org_a, "data.txt", b"abc\x00\x01\x02")

    assert response.status_code == 400


def test_rejects_empty_file(auth_client, alice, org_a):
    assert upload(auth_client(alice), org_a, "empty.txt", b"").status_code == 400


def test_rejects_file_over_the_size_limit(auth_client, alice, org_a, settings):
    settings.DOCUMENT_MAX_UPLOAD_BYTES = 100

    response = upload(auth_client(alice), org_a, "big.pdf", PDF_BYTES + b"x" * 200)

    assert response.status_code == 400


def test_rejects_request_without_file(auth_client, alice, org_a):
    response = auth_client(alice).post(list_url(org_a), {}, format="multipart")

    assert response.status_code == 400


# --- Duplicates --------------------------------------------------------------


def test_duplicate_content_in_same_organization_returns_409(auth_client, alice, org_a):
    client = auth_client(alice)
    first = upload(client, org_a, "a.txt", b"same content")

    second = upload(client, org_a, "b.txt", b"same content")

    assert second.status_code == 409
    assert second.json()["document_id"] == first.json()["id"]
    assert Document.objects.count() == 1


def test_same_content_is_allowed_in_different_organizations(auth_client, alice, bob, org_a, org_b):
    assert upload(auth_client(alice), org_a, "a.txt", b"same content").status_code == 201
    assert upload(auth_client(bob), org_b, "a.txt", b"same content").status_code == 201


# --- Tenant isolation --------------------------------------------------------


def test_user_cannot_access_documents_of_another_organization(
    auth_client, alice, bob, org_b, make_document
):
    document = make_document(org_b, uploaded_by=bob)
    client = auth_client(alice)

    assert client.get(list_url(org_b)).status_code == 404
    assert client.get(detail_url(org_b, document)).status_code == 404
    assert client.get(f"{detail_url(org_b, document)}download/").status_code == 404
    assert client.delete(detail_url(org_b, document)).status_code == 404
    assert upload(client, org_b).status_code == 404


def test_document_id_from_another_organization_is_not_found_under_own_organization(
    auth_client, alice, bob, org_a, org_b, make_document
):
    """Classic IDOR: own organization in the URL, someone else's document id."""
    foreign = make_document(org_b, uploaded_by=bob)

    response = auth_client(alice).get(detail_url(org_a, foreign))

    assert response.status_code == 404


def test_list_only_returns_documents_of_the_organization(
    auth_client, alice, bob, org_a, org_b, make_document
):
    mine = make_document(org_a, uploaded_by=alice)
    make_document(org_b, uploaded_by=bob)

    body = auth_client(alice).get(list_url(org_a)).json()

    assert body["count"] == 1
    assert [item["id"] for item in body["results"]] == [str(mine.id)]


def test_anonymous_requests_are_rejected(api_client, org_a):
    assert api_client.get(list_url(org_a)).status_code == 401
    assert api_client.post(list_url(org_a), {}, format="multipart").status_code == 401


# --- Download and delete -----------------------------------------------------


def test_download_returns_the_file_as_an_attachment(auth_client, alice, org_a, make_document):
    document = make_document(org_a, name="notes.txt", content=b"hello world")

    response = auth_client(alice).get(f"{detail_url(org_a, document)}download/")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"hello world"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in response["Content-Disposition"]


def test_member_cannot_delete_documents(auth_client, org_a, make_member, make_document):
    carol = make_member("carol@example.com", org_a, Membership.Role.MEMBER)
    document = make_document(org_a)

    response = auth_client(carol).delete(detail_url(org_a, document))

    assert response.status_code == 403
    assert Document.objects.filter(pk=document.pk).exists()


def test_owner_deletes_the_row_and_the_stored_file(
    auth_client, alice, org_a, make_document, django_capture_on_commit_callbacks
):
    document = make_document(org_a, uploaded_by=alice)
    stored_name = document.file.name

    with django_capture_on_commit_callbacks(execute=True):
        response = auth_client(alice).delete(detail_url(org_a, document))

    assert response.status_code == 204
    assert not Document.objects.filter(pk=document.pk).exists()
    assert not default_storage.exists(stored_name)
