import hashlib
import os

import jwt
from jwt import PyJWKClient
from rest_framework import status
from rest_framework.response import Response

from authn.models import Credential
from user.models import User


class AuthMiddleware:
    auth_endpoints = []
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    auth0_audience = os.getenv("AUTH0_AUDIENCE")
    jwks_endpoint = f"https://{auth0_domain}/.well-known/jwks.json"
    jwks_client = PyJWKClient(jwks_endpoint)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in self.auth_endpoints:
            bearer_token = request.headers.get('Authorization')
            if bearer_token is not None:
                access_token = bearer_token.split()[1]
                signing_key = self.jwks_client.get_signing_key_from_jwt(access_token)
                data = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=self.auth0_audience,
                )
                if not request.path.startsWith('api/v1/users'):
                    request.user = User.objects.get(auth0_id=data.sub)
            else:
                api_key = request.headers.get('X-API-Key')
                api_secret = request.headers.get('X-API-Secret')
                if api_key is None or api_secret is None:
                    return Response(status=status.HTTP_401_UNAUTHORIZED)
                else:
                    credential = Credential.objects.get(key=api_key)
                    api_secret_hash = hashlib.sha256((api_secret + credential.salt).encode())
                    if api_secret_hash is not credential.secret_hash:
                        return Response(status=status.HTTP_401_UNAUTHORIZED)
                    else:
                        if not request.path.startsWith('api/v1/users'):
                            request.user = User.objects.get(pk=credential.user_id)

        response = self.get_response(request)

        return response
