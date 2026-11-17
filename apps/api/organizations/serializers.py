from rest_framework import serializers

from organizations.models import Membership, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "created_at"]
        read_only_fields = fields


class MembershipSerializer(serializers.ModelSerializer):
    """A membership seen from the user's side: which organization, which role."""

    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["organization", "role"]


class MemberSerializer(serializers.ModelSerializer):
    """A membership seen from the organization's side: who belongs to it."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Membership
        fields = ["user_id", "email", "full_name", "role"]
