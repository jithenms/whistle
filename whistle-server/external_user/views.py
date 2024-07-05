import logging

from rest_framework.viewsets import ModelViewSet

from external_user.models import (
    ExternalUser,
)
from external_user.serializers import (
    ExternalUserSerializer,
)
from whistle_server.auth import (
    ServerAuth,
)


class ExternalUserViewSet(ModelViewSet):
    queryset = ExternalUser.objects.all()
    serializer_class = ExternalUserSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)
