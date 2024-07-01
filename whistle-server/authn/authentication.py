import hashlib
import hmac

import jwt
from django.conf import settings
from jwt import PyJWKClient
from keycove import decrypt
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission

from account.models import Account

jwks_client = PyJWKClient(settings.JWKS_ENDPOINT)


class ServerAuthentication(BaseAuthentication):
    def authenticate(self, request, *args, **kwargs):
        bearer_token = request.headers.get('Authorization')
        if bearer_token is not None:
            access_token = bearer_token.split()[1]
            signing_key = jwks_client.get_signing_key_from_jwt(access_token)
            try:
                data = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=settings.AUTH0_AUDIENCE,
                )
            except:
                raise exceptions.AuthenticationFailed()
            try:
                return Account.objects.get(auth0_id=data['sub']), None
            except Account.DoesNotExist:
                raise exceptions.AuthenticationFailed()
        else:
            api_key = request.headers.get('X-API-Key')
            api_secret = request.headers.get('X-API-Secret')
            if api_key is None or api_secret is None:
                raise exceptions.AuthenticationFailed()
            else:
                api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                try:
                    account = Account.objects.get(api_key_hash=api_key_hash)
                except Account.DoesNotExist:
                    raise exceptions.AuthenticationFailed()
                api_secret_hash = hashlib.sha256((api_secret + account.api_secret_salt).encode()).hexdigest()
                if api_secret_hash != account.api_secret_hash:
                    raise exceptions.AuthenticationFailed()
                else:
                    return account, None


class ClientAuthentication(BaseAuthentication):
    def authenticate(self, request, *args, **kwargs):
        bearer_token = request.headers.get('Authorization')
        if bearer_token is not None:
            access_token = bearer_token.split()[1]
            signing_key = jwks_client.get_signing_key_from_jwt(access_token)
            try:
                data = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=settings.AUTH0_AUDIENCE,
                )
            except:
                raise exceptions.AuthenticationFailed()
            return Account.objects.get(auth0_id=data['sub']), None
        else:
            api_key = request.headers.get('X-API-Key')
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            return Account.objects.get(api_key_hash=api_key_hash), None


class IsValidExternalId(BasePermission):
    def has_permission(self, request, view):
        external_id = request.headers.get('X-External-Id')
        external_id_hmac = request.headers.get('X-External-Id-Hmac')
        api_secret = decrypt(request.user.api_secret_encrypt, settings.WHISTLE_SECRET_KEY)
        if external_id is not None or external_id_hmac is not None:
            external_id_check = hmac.new(api_secret.encode(),
                                         external_id.encode(),
                                         hashlib.sha256).hexdigest()
            return external_id_check == external_id_hmac
        else:
            return False
