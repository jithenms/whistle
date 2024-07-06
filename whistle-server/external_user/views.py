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
from whistle_server.pagination import StandardLimitOffsetPagination


class ExternalUserViewSet(ModelViewSet):
    queryset = ExternalUser.objects.all()
    serializer_class = ExternalUserSerializer
    authentication_classes = [ServerAuth]
    pagination_class = StandardLimitOffsetPagination

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)
