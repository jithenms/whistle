import hashlib
import hmac

import jwt
from django.conf import settings
from jwt import PyJWKClient
from keycove import decrypt, generate_token, encrypt
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission

from user.models import User
from organization.models import Organization
from organization.models import OrganizationMember

jwks_client = PyJWKClient(settings.JWKS_ENDPOINT)


class ServerAuthentication(BaseAuthentication):
    def authenticate(self, request, *args, **kwargs):
        bearer_token = request.headers.get("Authorization")
        if bearer_token is not None:
            access_token = bearer_token.split()[1]
            signing_key = jwks_client.get_signing_key_from_jwt(access_token)
            try:
                data = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=["RS256"],
                )

                user = get_or_create_user(data)

                org = get_or_create_organization(data)

                member = get_or_create_organization_member(data, user, org)

                return org, None
            except (
                jwt.PyJWTError,
                Organization.DoesNotExist,
                User.DoesNotExist,
                OrganizationMember.DoesNotExist,
            ) as error:
                print(error)
                raise exceptions.AuthenticationFailed()
        else:
            api_key = request.headers.get("X-API-Key")
            api_secret = request.headers.get("X-API-Secret")
            if api_key is None or api_secret is None:
                raise exceptions.AuthenticationFailed()
            else:
                try:
                    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    org = Organization.objects.get(api_key_hash=api_key_hash)
                    api_secret_hash = hashlib.sha256(
                        (api_secret + org.api_secret_salt).encode()
                    ).hexdigest()
                    if api_secret_hash != org.api_secret_hash:
                        raise exceptions.AuthenticationFailed()
                    else:
                        return org, None
                except Organization.DoesNotExist as error:
                    print(error)
                    raise exceptions.AuthenticationFailed()


class ClientAuthentication(BaseAuthentication):
    def authenticate(self, request, *args, **kwargs):
        bearer_token = request.headers.get("Authorization")
        if bearer_token is not None:
            access_token = bearer_token.split()[1]
            signing_key = jwks_client.get_signing_key_from_jwt(access_token)
            try:
                data = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=["RS256"],
                )

                user = get_or_create_user(data)

                org = get_or_create_organization(data)

                member = get_or_create_organization_member(data, user, org)

                return org, None
            except (
                jwt.PyJWTError,
                Organization.DoesNotExist,
                User.DoesNotExist,
                OrganizationMember.DoesNotExist,
            ) as error:
                print(error)
                raise exceptions.AuthenticationFailed()
        else:
            api_key = request.headers.get("X-API-Key")
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            try:
                org = Organization.objects.get(api_key_hash=api_key_hash)
                return org, None
            except Organization.DoesNotExist as error:
                print(error)
                raise exceptions.AuthenticationFailed()


class IsValidExternalId(BasePermission):
    def has_permission(self, request, view):
        external_id = request.headers.get("X-External-Id")
        external_id_hmac = request.headers.get("X-External-Id-Hmac")
        api_secret = decrypt(
            request.user.api_secret_encrypt, settings.WHISTLE_SECRET_KEY
        )
        if external_id is not None or external_id_hmac is not None:
            external_id_check = hmac.new(
                api_secret.encode(), external_id.encode(), hashlib.sha256
            ).hexdigest()
            return external_id_check == external_id_hmac
        else:
            return False


def get_or_create_user(data):
    user, user_created = User.objects.get_or_create(
        clerk_user_id=data["user_id"],
        defaults={
            "full_name": data["full_name"],
            "email": data["primary_email"],
        },
    )
    return user


def get_or_create_organization(data):
    org, org_created = Organization.objects.get_or_create(
        clerk_org_id=data["org_id"],
        defaults={"slug": data["org_slug"], "name": data["org_name"]},
    )
    if org_created:
        (
            api_key_encrypt,
            api_key_hash,
            api_secret_encrypt,
            api_secret_hash,
            api_secret_salt,
        ) = generate_api_credentials()

        org.api_key_encrypt = api_key_encrypt
        org.api_key_hash = api_key_hash
        org.api_secret_encrypt = api_secret_encrypt
        org.api_secret_hash = api_secret_hash
        org.api_secret_salt = api_secret_salt
        org.save()
    return org


def get_or_create_organization_member(data, user, org):
    org_member, org_member_created = OrganizationMember.objects.get_or_create(
        organization=org, user=user, defaults={"role": data["org_role"]}
    )
    return org_member


def generate_api_credentials():
    api_key = generate_token(16)
    api_secret = generate_token(32)
    api_secret_salt = generate_token(8)
    api_key_encrypt = encrypt(api_key, settings.WHISTLE_SECRET_KEY)
    api_secret_encrypt = encrypt(api_secret, settings.WHISTLE_SECRET_KEY)
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    api_secret_hash = hashlib.sha256(
        (api_secret + api_secret_salt).encode()
    ).hexdigest()
    return (
        api_key_encrypt,
        api_key_hash,
        api_secret_encrypt,
        api_secret_hash,
        api_secret_salt,
    )
