import uuid

from django.db import models

from organization.models import Organization
from whistle import fields, utils
from whistle.fields import EncryptedFieldTypeChoices


class ExternalUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    external_id = models.CharField()
    first_name = fields.EncryptedField(
        EncryptedFieldTypeChoices.PERSONAL_DATA, null=True
    )
    first_name_hash = models.CharField(null=True)
    last_name = fields.EncryptedField(
        EncryptedFieldTypeChoices.PERSONAL_DATA, null=True
    )
    last_name_hash = models.CharField(null=True)
    email = fields.EncryptedField(EncryptedFieldTypeChoices.PERSONAL_DATA)
    email_hash = models.CharField()
    phone = fields.EncryptedField(EncryptedFieldTypeChoices.PERSONAL_DATA, null=True)
    phone_hash = models.CharField(null=True)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = [
            ["organization", "email_hash"],
            ["organization", "phone_hash"],
            ["organization", "external_id"],
        ]

    def save(self, *args, **kwargs):
        if self.first_name:
            self.first_name_hash = utils.perform_hash(self.first_name)
        if self.last_name:
            self.last_name_hash = utils.perform_hash(self.last_name)
        if self.email:
            self.email_hash = utils.perform_hash(self.email)
        if self.phone:
            self.phone_hash = utils.perform_hash(self.phone)
        super().save(*args, **kwargs)


class PlatformChoices(models.TextChoices):
    IOS = "IOS", "IOS"
    ANDROID = "ANDROID", "ANDROID"


class ExternalUserDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(ExternalUser, on_delete=models.CASCADE)
    token = models.CharField(unique=True)
    platform = models.CharField(choices=PlatformChoices.choices)
