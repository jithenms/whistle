import logging
import uuid

from django.db import models

from external_user.models import ExternalUser
from organization.models import Organization


class ExternalUserPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(ExternalUser, on_delete=models.CASCADE)
    slug = models.SlugField()

    class Meta:
        unique_together = [["organization", "slug"]]


class ChannelChoices(models.TextChoices):
    WEB = "WEB", "WEB"
    EMAIL = "EMAIL", "EMAIL"
    SMS = "SMS", "SMS"
    MOBILE_PUSH = "MOBILE_PUSH", "MOBILE_PUSH"


class ExternalUserPreferenceChannel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_preference = models.ForeignKey(
        ExternalUserPreference, related_name="channels", on_delete=models.CASCADE
    )
    slug = models.SlugField(choices=ChannelChoices.choices)
    enabled = models.BooleanField(default=False)
