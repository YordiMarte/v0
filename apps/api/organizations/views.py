from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from organizations.models import Organization
from organizations.serializers import MemberSerializer, OrganizationSerializer


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        # Scoped to the requesting user. An organization they do not belong to
        # is simply not in the queryset, so it answers 404 (not 403) and its
        # existence is not revealed.
        return Organization.objects.for_user(self.request.user)

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        organization = self.get_object()
        memberships = organization.memberships.select_related("user").order_by("user__full_name")
        return Response(MemberSerializer(memberships, many=True).data)
