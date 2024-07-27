from rest_framework.viewsets import ModelViewSet

from audience.models import Audience
from audience.serializers import AudienceSerializer
from whistle.auth import ServerAuth
from whistle.pagination import StandardLimitOffsetPagination


class AudienceViewSet(ModelViewSet):
    queryset = Audience.objects.all()
    serializer_class = AudienceSerializer
    authentication_classes = [ServerAuth]
    pagination_class = StandardLimitOffsetPagination

    def get_queryset(self):
        org = self.request.user
        return self.queryset.filter(organization=org)
