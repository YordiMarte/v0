from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from documents.models import Document
from documents.validators import validate_upload


class DocumentSerializer(serializers.ModelSerializer):
    """Output only. The storage path is deliberately not exposed."""

    uploaded_by = serializers.EmailField(
        source="uploaded_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = Document
        fields = [
            "id",
            "original_name",
            "content_type",
            "size_bytes",
            "status",
            "error_message",
            "uploaded_by",
            "created_at",
        ]


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(max_length=255)

    def validate_file(self, value):
        try:
            validate_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value
