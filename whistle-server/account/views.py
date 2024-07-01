import hashlib

from django.conf import settings
from django.http import JsonResponse
from keycove import generate_token, encrypt, decrypt
from rest_framework import mixins, viewsets, status
from rest_framework.generics import CreateAPIView, RetrieveAPIView

from account.models import Account
from account.serializers import AccountSerializer
from authn.authentication import ServerAuthentication


class AccountModelViewSet(viewsets.GenericViewSet):
    def get_object(self):
        return self.request.user


class AccountViewSet(CreateAPIView, RetrieveAPIView, mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     AccountModelViewSet
                     ):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    authentication_classes = [ServerAuthentication]

    def get_authenticators(self):
        if self.request.method == 'POST':
            return []
        return super(AccountViewSet, self).get_authenticators()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        api_key = generate_token(16)
        api_secret = generate_token(32)
        api_secret_salt = generate_token(8)

        api_key_encrypt = encrypt(api_key, settings.WHISTLE_SECRET_KEY)
        api_secret_encrypt = encrypt(api_secret, settings.WHISTLE_SECRET_KEY)

        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        api_secret_hash = hashlib.sha256((api_secret + api_secret_salt).encode()).hexdigest()

        serializer.save(api_key_encrypt=api_key_encrypt, api_key_hash=api_key_hash,
                        api_secret_encrypt=api_secret_encrypt, api_secret_hash=api_secret_hash,
                        api_secret_salt=api_secret_salt)
        response = JsonResponse({**serializer.data, 'api_key': api_key, 'api_secret': api_secret},
                                status=status.HTTP_201_CREATED)
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        api_key = decrypt(instance.api_key_encrypt, settings.WHISTLE_SECRET_KEY)
        api_secret = decrypt(instance.api_secret_encrypt, settings.WHISTLE_SECRET_KEY)
        serializer = self.get_serializer(instance)
        return JsonResponse({**serializer.data, 'api_key': api_key, 'api_secret': api_secret})
