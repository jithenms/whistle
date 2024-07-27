import logging

from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from external_user.models import (
    ExternalUser,
    ExternalUserDevice,
)
from external_user.serializers import (
    ExternalUserSerializer,
    ExternalUserDeviceSerializer,
)
from whistle.auth import (
    ServerAuth,
    ClientAuth,
    IsValidExternalId,
)
from whistle.pagination import StandardLimitOffsetPagination


class ExternalUserViewSet(ModelViewSet):
    queryset = ExternalUser.objects.all()
    serializer_class = ExternalUserSerializer
    authentication_classes = [ServerAuth]
    pagination_class = StandardLimitOffsetPagination

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class ExternalUserDeviceViewSet(ModelViewSet):
    queryset = ExternalUserDevice.objects.all()
    serializer_class = ExternalUserDeviceSerializer
    authentication_classes = [ClientAuth]
    permission_classes = [IsValidExternalId]

    def get_queryset(self):
        external_id = (
            self.request.headers.get("X-External-Id") if self.request else None
        )
        try:
            user = ExternalUser.objects.get(
                external_id=external_id,
                organization=self.request.user,
            )
        except ExternalUser.DoesNotExist:
            logging.error(
                "Invalid external id: %s provided for org: %s while querying preferences",
                external_id,
                self.request.user.id,
            )
            raise ValidationError(
                "Invalid External Id. Please provide a valid External Id in the request header.",
                "invalid_external_id",
            )
        return self.queryset.filter(user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"external_id": self.request.headers.get("X-External-Id")})
        return context
