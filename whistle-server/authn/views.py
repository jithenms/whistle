import hashlib
import secrets

from django.http import JsonResponse
from rest_framework import status, mixins
from rest_framework.generics import CreateAPIView
from rest_framework.viewsets import GenericViewSet

from authn.authentication import ServerAuthentication
from authn.models import Credential
from authn.serializers import CredentialSerializer


class CredentialViewSet(CreateAPIView, mixins.RetrieveModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin,
                        GenericViewSet):
    queryset = Credential.objects.all()
    serializer_class = CredentialSerializer
    authentication_classes = [ServerAuthentication]

    def get_queryset(self):
        return self.queryset.filter(account=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key = secrets.token_urlsafe(32)
        api_secret = secrets.token_urlsafe(32)
        salt = secrets.token_urlsafe(8)
        api_secret_hash = hashlib.sha256((api_secret + salt).encode()).hexdigest()
        serializer.save(account=request.user, api_key=api_key, api_secret_hash=api_secret_hash,
                        api_secret_hint=api_secret[:8])
        response = JsonResponse({**serializer.data, "api_secret": api_secret}, status=status.HTTP_201_CREATED)
        return response
