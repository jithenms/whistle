from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.viewsets import GenericViewSet

from organization.models import Organization, OrganizationCredentials
from organization.serializers import (
    OrganizationSerializer,
    OrganizationCredentialsSerializer,
)
from whistle.auth import ServerAuth


class OrganizationModelViewSet(viewsets.GenericViewSet):
    def get_object(self):
        return self.request.user


class OrganizationViewSet(RetrieveAPIView, OrganizationModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    authentication_classes = [ServerAuth]


class OrganizationCredentialsViewSet(RetrieveAPIView, GenericViewSet):
    queryset = OrganizationCredentials.objects.all()
    serializer_class = OrganizationCredentialsSerializer
    authentication_classes = [ServerAuth]
