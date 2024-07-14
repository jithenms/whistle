import logging

from rest_framework.viewsets import ModelViewSet

from audience.models import Audience
from audience.serializers import AudienceSerializer
from whistle_server.auth import ServerAuth


class AudienceViewSet(ModelViewSet):
    queryset = Audience.objects.all()
    serializer_class = AudienceSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        org = self.request.user
        return self.queryset.filter(organization=org)