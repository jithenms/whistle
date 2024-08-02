from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from organization.models import OrganizationCredentials
from organization.serializers import (
    OrganizationSerializer,
    OrganizationCredentialsSerializer,
)
from whistle.auth import ServerAuth
from whistle.utils import generate_api_credentials


class OrganizationViewSet(viewsets.GenericViewSet):
    serializer_class = OrganizationSerializer
    authentication_classes = [ServerAuth]

    def list(self, request, **kwargs):
        org = self.request.user
        serializer = self.get_serializer(org)
        return Response(serializer.data)


class OrganizationCredentialsViewSet(GenericViewSet):
    queryset = OrganizationCredentials.objects.all()
    serializer_class = OrganizationCredentialsSerializer
    authentication_classes = [ServerAuth]

    def list(self, request, **kwargs):
        instance = OrganizationCredentials.objects.get(organization=self.request.user)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(methods=["POST"], detail=False)
    def regenerate(self, request, **kwargs):
        instance = OrganizationCredentials.objects.get(organization=self.request.user)

        (
            api_key,
            api_secret,
            api_secret_salt,
        ) = generate_api_credentials()

        instance.api_key = api_key
        instance.api_secret = api_secret
        instance.api_secret_salt = api_secret_salt
        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)
