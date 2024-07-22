from rest_framework.viewsets import ModelViewSet

from external_user.models import (
    ExternalUser, ExternalUserDevice,
)
from external_user.serializers import (
    ExternalUserSerializer, ExternalUserDeviceSerializer,
)
from whistle_server.auth import (
    ServerAuth, ClientAuth,
)
from whistle_server.pagination import StandardLimitOffsetPagination


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

    def get_queryset(self):
        external_id = self.request.headers.get("X-External-Id")
        return self.queryset.filter(organization=self.request.user, external_id=external_id)

