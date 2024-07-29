import uuid

from django.db import models

from organization.models import Organization
from whistle import fields


class ProviderTypeChoices(models.TextChoices):
    SMS = "SMS", "SMS"
    EMAIL = "EMAIL", "EMAIL"
    PUSH = "PUSH", "PUSH"


class ProviderChoices(models.TextChoices):
    TWILIO = "TWILIO", "TWILIO"
    SENDGRID = (
        "SENDGRID",
        "SENDGRID",
    )
    APNS = "APNS", "APNS"
    FCM = "FCM", "FCM"


class Provider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    provider_type = models.CharField(choices=ProviderTypeChoices.choices)
    provider = models.CharField(choices=ProviderChoices.choices)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [
            ["organization", "provider"],
        ]


class ProviderCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="credentials"
    )
    slug = models.SlugField()
    value = fields.EncryptedField(key_id="alias/APICredentials")

    class Meta:
        unique_together = [
            ["provider", "slug"],
        ]
