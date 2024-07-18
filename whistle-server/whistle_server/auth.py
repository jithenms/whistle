import hashlib
import hmac
import logging

import jwt
from django.conf import settings
from jwt import PyJWKClient
from keycove import decrypt, generate_token, encrypt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework.permissions import BasePermission

from organization.models import Organization
from organization.models import OrganizationMember
from user.models import User

jwks_client = PyJWKClient(settings.WHISTLE_JWKS_ENDPOINT)


class ServerAuth(BaseAuthentication):
    def authenticate(self, request, *args, **kwargs):
        bearer_token = request.headers.get("Authorization", None)
        if bearer_token is not None:
            bearer_token = bearer_token.split()
            if not len(bearer_token) == 2 or bearer_token[0] != "Bearer":
                raise ValidationError(
                    "Access token is missing. Please provide your Access token in the request header.",
                    "missing_access_token",
                )
            access_token = bearer_token[1]
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(access_token)

                data = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=["RS256"],
                )

                user = update_or_create_user(data)

                org = update_or_create_organization(data)

                member = update_or_create_organization_member(data, user, org)

                return org, None
            except jwt.PyJWTError as error:
                logging.debug("Access token invalid with error: %s", error)
                raise AuthenticationFailed(
                    "The provided access token is invalid. Please provide a valid access token.",
                    "invalid_access_token",
                )
        else:
            api_key = request.headers.get("X-API-Key")
            api_secret = request.headers.get("X-API-Secret")
            if api_key is None and api_secret is None:
                raise ValidationError(
                    "No credentials provided. Please provide either an access token or an API key and API secret in "
                    "the request header.",
                    "missing_credentials",
                )
            elif api_key is None:
                raise ValidationError(
                    "API key is missing. Please provide your API key in the request header.",
                    "missing_api_key",
                )
            elif api_secret is None:
                raise ValidationError(
                    "API secret is missing. Please provide your API secret in the request header.",
                    "missing_api_secret",
                )
            else:
                try:
                    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    org = Organization.objects.get(api_key_hash=api_key_hash)
                    api_secret_hash = hashlib.sha256(
                        (api_secret + org.api_secret_salt).encode()
                    ).hexdigest()
                    if api_secret_hash != org.api_secret_hash:
                        logging.debug(
                            "API secret invalid for org: %s",
                            org.id,
                        )
                        raise AuthenticationFailed(
                            "API secret invalid. You can find your API secret in Whistle settings.",
                            "invalid_api_secret",
                        )
                    else:
                        return org, None
                except Organization.DoesNotExist:
                    logging.debug(
                        "API key invalid."
                    )
                    raise AuthenticationFailed(
                        "API key invalid. You can find your API key in Whistle settings.",
                        "invalid_api_key",
                    )


class ClientAuth(BaseAuthentication):
    def authenticate(self, request, *args, **kwargs):
        bearer_token = request.headers.get("Authorization")
        if bearer_token is not None:
            bearer_token = bearer_token.split()
            if not len(bearer_token) == 2 or bearer_token[0] != "Bearer":
                raise ValidationError(
                    "Access token is missing. Please provide your Access token in the request header.",
                    "missing_access_token",
                )
            access_token = bearer_token[1]

            signing_key = jwks_client.get_signing_key_from_jwt(access_token)
            try:
                data = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=["RS256"],
                )

                user = update_or_create_user(data)

                org = update_or_create_organization(data)

                member = update_or_create_organization_member(data, user, org)

                return org, None
            except jwt.PyJWTError:
                logging.debug(
                    "Access token invalid."
                )
                raise AuthenticationFailed(
                    "The provided access token is invalid. Please provide a valid access token.",
                    "invalid_access_token",
                )
        else:
            api_key = request.headers.get("X-API-Key")
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            try:
                org = Organization.objects.get(api_key_hash=api_key_hash)
                return org, None
            except Organization.DoesNotExist:
                logging.debug(
                    "Invalid API Key provided"
                )
                raise AuthenticationFailed(
                    "API key invalid. You can find your API key in Whistle settings.",
                    "invalid_api_key",
                )


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
            if external_id_check == external_id_hmac:
                return True
            else:
                self.message = (
                    "External ID HMAC invalid. Please ensure you are generating the HMAC correctly "
                    "using your API Secret and try again."
                )
                self.code = "invalid_external_id_hmac"
                logging.debug(
                    "Invalid External Id HMAC provided for org: %s",
                    request.user.id,
                )
        elif external_id is not None and external_id_hmac is None:
            self.message = (
                "No External ID Hmac provided. Please ensure you are generating an Hmac "
                "using your secret key and try again."
            )
            self.code = "missing_external_id_hmac"
            logging.debug("External Id Hmac not provided for org: %s", request.user.id)
            return False
        else:
            self.message = "No External ID provided. Please include a valid External ID to identify the user."
            self.code = "missing_external_id"
            logging.debug("No External Id provided for org: %s", request.user.id)
            return False


def update_or_create_user(data):
    user, user_created = User.objects.update_or_create(
        clerk_user_id=data["user_id"],
        defaults={
            "full_name": data["full_name"],
            "email": data["primary_email"],
        },
    )

    if user_created:
        logging.info("New user with clerk id: %s synced.", user.clerk_user_id)

    return user


def update_or_create_organization(data):
    org, org_created = Organization.objects.update_or_create(
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

        logging.info("New organization with clerk id: %s synced.", data["org_id"])
    return org


def update_or_create_organization_member(data, user, org):
    org_member, org_member_created = OrganizationMember.objects.update_or_create(
        organization=org, user=user, defaults={"role": data["org_role"]}
    )

    if org_member_created:
        logging.info("New organization member with clerk id: %s in clerk org: %s synced.",
                     user.clerk_user_id,
                     org.clerk_org_id)

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
