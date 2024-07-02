from rest_framework.viewsets import ModelViewSet

from external_user.models import (
    ExternalUser,
    ExternalUserPreference,
    ExternalUserSubscription,
)
from external_user.serializers import (
    ExternalUserSerializer,
    ExternalUserPreferenceSerializer,
    ExternalUserSubscriptionSerializer,
)
from whistle_server.middleware import (
    ServerAuthentication,
    ClientAuthentication,
    IsValidExternalId,
)


class ExternalUserViewSet(ModelViewSet):
    queryset = ExternalUser.objects.all()
    serializer_class = ExternalUserSerializer
    authentication_classes = [ServerAuthentication]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class ExternalUserPreferenceViewSet(ModelViewSet):
    queryset = ExternalUserPreference.objects.all()
    serializer_class = ExternalUserPreferenceSerializer
    authentication_classes = [ClientAuthentication]
    permission_classes = [IsValidExternalId]

    def get_queryset(self):
        user = ExternalUser.objects.get(
            external_id=self.request.headers.get("X-External-Id"),
            organization=self.request.user,
        )
        return self.queryset.filter(user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"external_id": self.request.headers.get("X-External-Id")})
        return context


class ExternalUserSubscriptionViewSet(ModelViewSet):
    queryset = ExternalUserSubscription.objects.all()
    serializer_class = ExternalUserSubscriptionSerializer
    authentication_classes = [ClientAuthentication]
    permission_classes = [IsValidExternalId]

    def get_queryset(self):
        user = ExternalUser.objects.get(
            external_id=self.request.headers.get("X-External-Id"),
            organization=self.request.user,
        )
        return self.queryset.filter(user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"external_id": self.request.headers.get("X-External-Id")})
        return context
