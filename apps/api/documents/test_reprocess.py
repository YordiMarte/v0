import pytest

from documents.models import Document

pytestmark = pytest.mark.django_db


def reprocess_url(org, document) -> str:
    return f"/api/organizations/{org.id}/documents/{document.id}/reprocess/"


def test_failed_document_is_queued_again(auth_client, alice, org_a, make_document):
    document = make_document(org_a, uploaded_by=alice)
    Document.objects.filter(pk=document.pk).update(
        status=Document.Status.FAILED, error_message="boom"
    )

    response = auth_client(alice).post(reprocess_url(org_a, document))

    assert response.status_code == 202
    document.refresh_from_db()
    assert document.status == Document.Status.PENDING
    assert document.error_message == ""


@pytest.mark.parametrize("state", [Document.Status.PENDING, Document.Status.READY])
def test_only_failed_documents_can_be_reprocessed(auth_client, alice, org_a, make_document, state):
    document = make_document(org_a, uploaded_by=alice)
    Document.objects.filter(pk=document.pk).update(status=state)

    response = auth_client(alice).post(reprocess_url(org_a, document))

    assert response.status_code == 409


def test_cannot_reprocess_a_document_of_another_organization(
    auth_client, alice, bob, org_b, make_document
):
    document = make_document(org_b, uploaded_by=bob)
    Document.objects.filter(pk=document.pk).update(status=Document.Status.FAILED)

    assert auth_client(alice).post(reprocess_url(org_b, document)).status_code == 404
