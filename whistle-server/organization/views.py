from django.conf import settings
from django.http import JsonResponse
from keycove import decrypt
from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView

from organization.models import Organization
from organization.serializers import OrganizationSerializer
from whistle_server.middleware import ServerAuthentication


class OrganizationModelViewSet(viewsets.GenericViewSet):
    def get_object(self):
        return self.request.user


class OrganizationViewSet(RetrieveAPIView, OrganizationModelViewSet):
    lookup_field = "clerk_org_id"
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    authentication_classes = [ServerAuthentication]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        api_key = decrypt(instance.api_key_encrypt, settings.WHISTLE_SECRET_KEY)
        api_secret = decrypt(instance.api_secret_encrypt, settings.WHISTLE_SECRET_KEY)
        serializer = self.get_serializer(instance)
        return JsonResponse(
            {**serializer.data, "api_key": api_key, "api_secret": api_secret}
        )
