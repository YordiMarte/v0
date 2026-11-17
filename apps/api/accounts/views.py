from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import MeSerializer, RegisterSerializer, UserSerializer
from accounts.services import register_owner
from organizations.serializers import OrganizationSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]
    # A stale or invalid Authorization header must not break public registration.
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user, organization = register_owner(**serializer.validated_data)
        except IntegrityError:
            # Two simultaneous sign-ups with the same email: the database
            # constraint is the real guard, the serializer check is a courtesy.
            raise serializers.ValidationError(
                {"email": ["An account with this email already exists."]}
            ) from None

        return Response(
            {
                "user": UserSerializer(user).data,
                "organization": OrganizationSerializer(organization).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class MeView(APIView):
    def get(self, request):
        user = User.objects.prefetch_related("memberships__organization").get(pk=request.user.pk)
        return Response(MeSerializer(user).data)
