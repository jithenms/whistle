import base64
import hashlib
import hmac
import os

import jwt
from jwt import PyJWKClient
from keycove import decrypt
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission

from account.models import Account
from account.serializers import AccountSerializer

api_secret_key = os.getenv('API_SECRET_KEY')
auth0_domain = os.getenv("AUTH0_DOMAIN")
auth0_audience = os.getenv("AUTH0_AUDIENCE")
jwks_endpoint = f"{auth0_domain}/.well-known/jwks.json"
jwks_client = PyJWKClient(jwks_endpoint)
user_serializer = AccountSerializer


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
                    audience=auth0_audience,
                )
            except:
                raise exceptions.AuthenticationFailed()
            return Account.objects.get(auth0_id=data['sub']), None
        else:
            api_key = request.headers.get('X-API-Key')
            api_secret = request.headers.get('X-API-Secret')
            if api_key is None or api_secret is None:
                raise exceptions.AuthenticationFailed()
            else:
                api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                account = Account.objects.get(api_key_hash=api_key_hash)
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
                    audience=auth0_audience,
                )
            except:
                raise exceptions.AuthenticationFailed()
            return Account.objects.get(auth0_id=data['sub']), None
        else:
            api_key = request.headers.get('X-API-Key')
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            return Account.objects.get(api_key_hash=api_key_hash), None


class IsValidExternalUserId(BasePermission):
    def has_permission(self, request, view):
        external_id = request.headers.get('X-External-Id')
        external_id_hmac = request.headers.get('X-External-Id-Hmac')
        api_secret = decrypt(request.user.api_secret_encrypt, api_secret_key)
        if external_id is not None or external_id_hmac is not None:
            external_id_check = hmac.new(api_secret.encode(),
                                         external_id.encode(),
                                         hashlib.sha256).hexdigest()
            return external_id_check == external_id_hmac
        else:
            return False
