import hashlib
import hmac
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.conf import settings
from jwt import PyJWKClient

from external_user.models import ExternalUser
from organization.models import OrganizationCredentials
from whistle import utils

jwks_client = PyJWKClient(settings.JWKS_ENDPOINT_URL)


class ClientAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        params = parse_qs(scope["query_string"])
        headers = dict(scope["headers"])
        if (
            b"sec-websocket-protocol" in headers
            and b"external_id" in params
            and b"external_id_hmac" in params
        ):
            api_key = headers[b"sec-websocket-protocol"].decode()
            scope["api_key"] = api_key
            api_key_hash = utils.perform_hash(api_key)
            credentials = await get_organization_credentials(api_key_hash=api_key_hash)
            if credentials:
                external_id = params[b"external_id"][0].decode()
                external_id_hmac = params[b"external_id_hmac"][0].decode()
                external_id_check = hmac.new(
                    credentials.api_secret.encode(),
                    external_id.encode(),
                    hashlib.sha256,
                ).hexdigest()
                if external_id_check == external_id_hmac:
                    external_user = await get_external_user(
                        organization=credentials.organization, external_id=external_id
                    )
                    if external_user:
                        scope["external_user"] = external_user
                        scope["org"] = credentials.organization
                    else:
                        scope["error_code"] = "user_not_found"
                        scope["error_reason"] = (
                            "User with this External ID not found. Please verify the External ID and "
                            "ensure the user is registered with Whistle."
                        )
                        logging.debug(
                            "User not found with external id: %s for org: %s while trying to connect websocket",
                            external_id,
                            credentials.organization.id,
                        )
                else:
                    scope["error_reason"] = (
                        "External ID HMAC invalid. Please ensure you are generating the HMAC correctly "
                        "using your API Secret and try again."
                    )
                    scope["error_code"] = "invalid_external_id_hmac"
                    logging.debug(
                        "Invalid External Id HMAC provided while trying to connect websocket for org: %s",
                        credentials.organization.id,
                    )
            else:
                scope["error_code"] = "invalid_api_key"
                scope["error_reason"] = (
                    "API key invalid. You can find your API key in Whistle settings."
                )
                logging.debug(
                    "Invalid API Key provided while trying to connect websocket"
                )
        elif b"sec-websocket-protocol" not in headers:
            scope["error_code"] = "missing_api_key"
            scope["error_reason"] = (
                "API key is missing. Please provide your API key in the request header."
            )
        elif b"external_id_hmac" not in headers:
            scope["error_reason"] = (
                "No External ID Hmac provided. Please ensure you are generating an Hmac "
                "using your secret key and try again."
            )
            scope["error_code"] = "missing_external_id_hmac"
        else:
            scope["error_reason"] = (
                "No External ID provided. Please include a valid External ID to identify the user."
            )
            scope["error_code"] = "missing_external_id"
        return await self.app(scope, receive, send)


@database_sync_to_async
def get_organization_credentials(**kwargs):
    try:
        return OrganizationCredentials.objects.select_related("organization").get(
            **kwargs
        )
    except OrganizationCredentials.DoesNotExist:
        return None


@database_sync_to_async
def get_external_user(**kwargs):
    try:
        return ExternalUser.objects.get(**kwargs)
    except ExternalUser.DoesNotExist:
        return None
