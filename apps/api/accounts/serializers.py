from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User
from organizations.serializers import MembershipSerializer


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    full_name = serializers.CharField(max_length=150)
    organization_name = serializers.CharField(max_length=150)

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate(self, attrs):
        # Validate the password against the user's own data (e.g. too similar to the email).
        candidate = User(email=attrs["email"], full_name=attrs["full_name"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name"]
        read_only_fields = fields


class MeSerializer(serializers.ModelSerializer):
    memberships = MembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "memberships"]
        read_only_fields = fields
