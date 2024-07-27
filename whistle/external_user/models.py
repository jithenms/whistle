import uuid

from django.db import models

from organization.models import Organization
from whistle import utils

from whistle.utils import EncryptedField


class ExternalUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    external_id = models.CharField(max_length=255, unique=True)

    first_name = EncryptedField(key_id="alias/PersonalData", max_length=255, blank=True)
    first_name_hash = models.CharField(max_length=64, blank=True, editable=False)

    last_name = EncryptedField(key_id="alias/PersonalData", max_length=255, blank=True)
    last_name_hash = models.CharField(max_length=64, blank=True, editable=False)

    email = EncryptedField(key_id="alias/PersonalData", max_length=255)
    email_hash = models.CharField(max_length=64, unique=True)

    phone = EncryptedField(key_id="alias/PersonalData", max_length=255, blank=True)
    phone_hash = models.CharField(max_length=64, blank=True, editable=False)

    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = [
            ["organization", "email_hash"],
            ["organization", "phone_hash"],
            ["organization", "external_id"],
        ]

    def save(self, *args, **kwargs):
        if self.first_name:
            self.first_name_hash = utils.hash_value(self.first_name)
        if self.last_name:
            self.last_name_hash = utils.hash_value(self.last_name)
        if self.email:
            self.email_hash = utils.hash_value(self.email)
        if self.phone:
            self.phone_hash = utils.hash_value(self.phone)
        super().save(*args, **kwargs)


class PlatformChoices(models.TextChoices):
    IOS = "IOS", "IOS"
    ANDROID = "ANDROID", "ANDROID"


class ExternalUserDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(ExternalUser, on_delete=models.CASCADE)
    bundle_id = models.CharField(blank=True, unique=True)
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=255, choices=PlatformChoices.choices)
