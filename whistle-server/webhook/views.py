import hashlib

from django.conf import settings
from django.http import HttpResponse
from keycove import generate_token, encrypt
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.viewsets import GenericViewSet
from svix import Webhook, WebhookVerificationError

from organization.models import Organization, OrganizationMember
from user.models import User


class ClerkWebhookViewSet(CreateAPIView, GenericViewSet):
    def create(self, request, *args, **kwargs):
        headers = request.headers
        payload = request.body

        try:
            wh = Webhook(settings.CLERK_WEBHOOK_SECRET)
            msg = wh.verify(payload, headers)
        except WebhookVerificationError as e:
            print(e)
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

        match msg["type"]:
            case "user.created":
                create_user(msg)
            case "organization.created":
                create_org(msg)
            case "organizationMembership.created":
                create_org_member(msg)
            # todo handle updates to metadata
            case _:
                pass

        return HttpResponse(status=status.HTTP_204_NO_CONTENT)


def create_user(msg):
    User.objects.create(
        clerk_user_id=msg["data"]["id"],
        first_name=msg["data"].get("first_name", None),
        last_name=msg["data"].get("last_name", None),
        email=msg["data"].get("email_addresses", [{}])[0].get("email_address", None),
    )


def create_org(msg):
    (
        api_key_encrypt,
        api_key_hash,
        api_secret_encrypt,
        api_secret_hash,
        api_secret_salt,
    ) = generate_api_credentials()
    Organization.objects.create(
        clerk_org_id=msg["data"]["id"],
        name=msg["data"]["name"],
        slug=msg["data"]["slug"],
        api_key_encrypt=api_key_encrypt,
        api_key_hash=api_key_hash,
        api_secret_encrypt=api_secret_encrypt,
        api_secret_hash=api_secret_hash,
        api_secret_salt=api_secret_salt,
    )


def create_org_member(msg):
    org = Organization.objects.get(clerk_org_id=msg["data"]["organization"]["id"])
    user = User.objects.get(clerk_user_id=msg["data"]["public_user_data"]["user_id"])
    OrganizationMember.objects.create(organization=org, user=user)


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
