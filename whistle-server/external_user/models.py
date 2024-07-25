import logging
import uuid

from django.db import models

from organization.models import Organization


class ExternalUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    email = models.CharField(max_length=255)
    phone = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = [
            ["organization", "email"],
            ["organization", "phone"],
            ["organization", "external_id"],
        ]

    def delete(self, using=None, keep_parents=False):
        response = super().delete(using, keep_parents)
        logging.info(
            "External user with id: %s deleted for org: %s",
            self.id,
            self.organization.id,
        )
        return response


class PlatformChoices(models.TextChoices):
    IOS = "IOS", "IOS"
    ANDROID = "ANDROID", "ANDROID"


class ExternalUserDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(ExternalUser, on_delete=models.CASCADE)
    bundle_id = models.CharField(blank=True, unique=True)
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=255, choices=PlatformChoices.choices)
