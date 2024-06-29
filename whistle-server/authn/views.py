import hashlib
import secrets

from django.http import JsonResponse
from rest_framework import status, renderers
from rest_framework.generics import CreateAPIView
from rest_framework.viewsets import GenericViewSet

from authn.models import Credential
from authn.serializers import CredentialSerializer


class CredentialViewSet(CreateAPIView, GenericViewSet):
    queryset = Credential.objects.all()
    serializer_class = CredentialSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse({'error': 'failed_to_create_credential', 'error_description': "Invalid input"},
                                status=status.HTTP_400_BAD_REQUEST)

        api_key = secrets.token_urlsafe(32)
        api_secret = secrets.token_urlsafe(32)
        salt = secrets.token_urlsafe(8)

        api_secret_hash = hashlib.sha256((api_secret + salt).encode()).hexdigest()

        serializer.save(account=request.account, api_key=api_key, api_secret_hash=api_secret_hash,
                        api_secret_hint=api_secret[:8], salt=salt)

        response = JsonResponse({**serializer.data, "api_secret": api_secret}, status=status.HTTP_201_CREATED,
                                safe=False)
        return response
