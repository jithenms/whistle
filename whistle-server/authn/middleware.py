import hashlib
import os

import jwt
from django.http import JsonResponse
from jwt import PyJWKClient
from rest_framework import status

from authn.models import Application
from user.models import User
from user.serializers import UserSerializer

auth_error_msg = {
    'error': 'access_denied',
    'error_description': 'Unauthorized'
}


class AuthMiddleware:
    auth_endpoints = {
        '/api/v1/users/': {'methods': ['GET']},
        '/api/v1/applications/': {'methods': ['POST']},
    }
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    auth0_audience = os.getenv("AUTH0_AUDIENCE")
    jwks_endpoint = f"{auth0_domain}/.well-known/jwks.json"
    jwks_client = PyJWKClient(jwks_endpoint)
    user_serializer = UserSerializer

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in self.auth_endpoints and request.method in self.auth_endpoints[request.path]['methods']:
            bearer_token = request.headers.get('Authorization')
            if bearer_token is not None:
                access_token = bearer_token.split()[1]
                signing_key = self.jwks_client.get_signing_key_from_jwt(access_token)
                try:
                    data = jwt.decode(
                        access_token,
                        signing_key.key,
                        algorithms=["RS256"],
                        audience=self.auth0_audience,
                    )
                except:
                    response = JsonResponse(auth_error_msg, status=status.HTTP_401_UNAUTHORIZED)
                    return response
                request._user = User.objects.get(auth0_id=data['sub'])
            else:
                api_key = request.headers.get('X-API-Key')
                api_secret = request.headers.get('X-API-Secret')
                if api_key is None or api_secret is None:
                    response = JsonResponse(auth_error_msg, status=status.HTTP_401_UNAUTHORIZED)
                    return response
                else:
                    application = Application.objects.get(api_key=api_key)
                    api_secret_hash = hashlib.sha256((api_secret + application.salt).encode()).hexdigest()
                    if api_secret_hash != application.api_secret_hash:
                        response = JsonResponse(auth_error_msg, status=status.HTTP_401_UNAUTHORIZED)
                        return response
                    else:
                        request._user = application.user

        response = self.get_response(request)

        return response
