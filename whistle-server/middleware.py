import datetime
from datetime import datetime

import os
import jwt
from jwt import PyJWKClient
import pytz
import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from jwt.algorithms import RSAAlgorithm
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from account.models import Account


CLERK_API_URL = "https://api.clerk.com/v1"
CLERK_FRONTEND_API_URL = os.getenv("CLERK_FRONTEND_API_URL")
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
CACHE_KEY = "jwks_data"

jwks_client = PyJWKClient(f"{CLERK_FRONTEND_API_URL}/.well-known/jwks.json")


class JWTAuthenticationMiddleware(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            raise AuthenticationFailed("Bearer token not provided.")
        user = self.decode_jwt(token)
        clerk = ClerkSDK()
        info, found = clerk.fetch_user_info(user.clerk_id)
        if not user:
            return None
        else:
            if found:
                user.org_id = info["org_id"]
                user.email = info["email"]
                user.first_name = info["first_name"]
                user.last_name = info["last_name"]
                user.last_login = info["last_login"]
            user.save()

        return user, None

    def decode_jwt(self, token):
        public_key = jwks_client.get_signing_key_from_jwt(token)
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_signature": True},
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired.")
        except jwt.DecodeError as e:
            raise AuthenticationFailed("Token decode error.")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid token.")

        user_id = payload.get("sub")
        if user_id:
            return Account.objects.get(clerk_id=user_id)
        return None

class ClerkSDK:
    def fetch_user_info(self, clerk_id: str):
        response = requests.get(
            f"{CLERK_API_URL}/users/{clerk_id}",
            headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "org_id": data["organization_id"],
                "email_address": data["email_addresses"][0]["email_address"],
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "last_login": datetime.datetime.fromtimestamp(
                    data["last_sign_in_at"] / 1000, tz=pytz.UTC
                ),
            }, True
        else:
            return {
                "org_id": "",
                "email_address": "",
                "first_name": "",
                "last_name": "",
                "last_login": None,
            }, False