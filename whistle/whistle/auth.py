import hashlib
import hmac
import logging

import jwt
from django.conf import settings
from django.db import transaction
from jwt import PyJWKClient
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework.permissions import BasePermission

from organization.models import Organization, OrganizationCredentials
from organization.models import OrganizationMember
from user.models import User
from whistle import utils
from whistle.utils import generate_api_credentials

jwks_client = PyJWKClient(settings.JWKS_ENDPOINT_URL)


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
            if not api_key and not api_secret:
                raise ValidationError(
                    "No credentials provided. Please provide either an access token or an API key and API secret in "
                    "the request header.",
                    "missing_credentials",
                )
            elif not api_key:
                raise ValidationError(
                    "API key is missing. Please provide your API key in the request header.",
                    "missing_api_key",
                )
            elif not api_secret:
                raise ValidationError(
                    "API secret is missing. Please provide your API secret in the request header.",
                    "missing_api_secret",
                )
            else:
                try:
                    api_key_hash = utils.perform_hash(api_key)
                    credentials = OrganizationCredentials.objects.select_related(
                        "organization"
                    ).get(api_key_hash=api_key_hash)
                    api_secret_hash = utils.perform_hash(
                        api_secret, credentials.api_secret_salt
                    )
                    if api_secret_hash != credentials.api_secret_hash:
                        logging.debug(
                            "API secret invalid for org: %s",
                            credentials.organization.id,
                        )
                        raise AuthenticationFailed(
                            "API secret invalid. You can find your API secret in Whistle settings.",
                            "invalid_api_secret",
                        )
                    else:
                        return credentials.organization, None
                except OrganizationCredentials.DoesNotExist:
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
                logging.debug("Access token invalid.")
                raise AuthenticationFailed(
                    "The provided access token is invalid. Please provide a valid access token.",
                    "invalid_access_token",
                )
        else:
            api_key = request.headers.get("X-API-Key")
            api_key_hash = utils.perform_hash(api_key)
            try:
                credentials = OrganizationCredentials.objects.select_related(
                    "organization"
                ).get(api_key_hash=api_key_hash)
                return credentials.organization, None
            except OrganizationCredentials.DoesNotExist:
                logging.debug("Invalid API Key provided")
                raise AuthenticationFailed(
                    "API key invalid. You can find your API key in Whistle settings.",
                    "invalid_api_key",
                )


class IsValidExternalId(BasePermission):

    def has_permission(self, request, view):
        external_id = request.headers.get("X-External-Id")
        external_id_hmac = request.headers.get("X-External-Id-Hmac")
        credentials = OrganizationCredentials.objects.get(organization=request.user)
        if external_id or external_id_hmac:
            external_id_check = hmac.new(
                credentials.api_secret.encode(), external_id.encode(), hashlib.sha256
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
        elif external_id and not external_id_hmac:
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
    user, user_created = User.objects.update_or_create(clerk_user_id=data["user_id"])

    if user_created:
        logging.info("New user with clerk id: %s synced.", user.clerk_user_id)

    return user


@transaction.atomic
def update_or_create_organization(data):
    org, org_created = Organization.objects.update_or_create(
        clerk_org_id=data["org_id"],
        defaults={"slug": data["org_slug"], "name": data["org_name"]},
    )
    if org_created:
        (
            api_key,
            api_secret,
            api_secret_salt,
        ) = generate_api_credentials()

        OrganizationCredentials.objects.create(
            organization=org,
            api_key=api_key,
            api_secret=api_secret,
            api_secret_salt=api_secret_salt,
        )

        logging.info("New organization with clerk id: %s synced.", data["org_id"])
    return org


def update_or_create_organization_member(data, user, org):
    org_member, org_member_created = OrganizationMember.objects.update_or_create(
        organization=org, user=user, defaults={"role": data["org_role"]}
    )

    if org_member_created:
        logging.info(
            "New organization member with clerk id: %s in clerk org: %s synced.",
            user.clerk_user_id,
            org.clerk_org_id,
        )

    return org_member
