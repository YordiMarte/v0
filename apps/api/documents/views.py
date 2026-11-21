from functools import cached_property

from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from documents.models import Document
from documents.serializers import DocumentSerializer, DocumentUploadSerializer
from documents.services import DuplicateDocument, create_document
from organizations.models import Membership, Organization


class DocumentPagination(PageNumberPagination):
    page_size = 20


class UploadRateThrottle(UserRateThrottle):
    scope = "upload"


class DocumentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DocumentSerializer
    pagination_class = DocumentPagination
    parser_classes = [MultiPartParser]

    @cached_property
    def organization(self) -> Organization:
        # Not a member (or it does not exist): 404, so existence is not revealed.
        return get_object_or_404(
            Organization.objects.for_user(self.request.user), pk=self.kwargs["org_id"]
        )

    @cached_property
    def membership(self) -> Membership:
        return Membership.objects.get(user=self.request.user, organization=self.organization)

    def get_queryset(self):
        # Always scoped to the organization from the URL, so a document id from
        # another organization is simply not found.
        return Document.objects.filter(organization=self.organization).select_related("uploaded_by")

    def get_throttles(self):
        if self.action == "create":
            return [UploadRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        organization = self.organization
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            document = create_document(
                organization=organization,
                uploaded_by=request.user,
                upload=serializer.validated_data["file"],
            )
        except DuplicateDocument as exc:
            return Response(
                {
                    "detail": "This file has already been uploaded to the organization.",
                    "document_id": str(exc.document_id),
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def download(self, request, *args, **kwargs):
        document = self.get_object()
        response = FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.original_name,
            content_type=document.content_type,
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def reprocess(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).select_for_update(of=("self",))
        with transaction.atomic():
            document = get_object_or_404(queryset, pk=self.kwargs["pk"])
            self.check_object_permissions(request, document)
            if document.status != Document.Status.FAILED:
                return Response(
                    {"detail": "Only failed documents can be reprocessed."},
                    status=status.HTTP_409_CONFLICT,
                )

            document.status = Document.Status.PENDING
            document.error_message = ""
            document.save(update_fields=["status", "error_message", "updated_at"])

        return Response(DocumentSerializer(document).data, status=status.HTTP_202_ACCEPTED)

    def perform_destroy(self, instance):
        if self.membership.role == Membership.Role.MEMBER:
            raise PermissionDenied("Only owners and admins can delete documents.")

        storage = instance.file.storage
        name = instance.file.name
        with transaction.atomic():
            instance.delete()
            # Remove the file only once the row deletion is committed.
            transaction.on_commit(lambda: storage.delete(name))
