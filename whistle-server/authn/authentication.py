import hashlib
import os

import jwt
from jwt import PyJWKClient
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from authn.models import Credential
from account.models import Account
from account.serializers import AccountSerializer

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
                credential = Credential.objects.get(api_key=api_key)
                api_secret_hash = hashlib.sha256((api_secret + credential.salt).encode()).hexdigest()
                if api_secret_hash != credential.api_secret_hash:
                    raise exceptions.AuthenticationFailed()
                else:
                    return credential.account, None


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
            credential = Credential.objects.get(api_key=api_key)
            return credential.account, None
