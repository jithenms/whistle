import logging
import uuid

from django.db import models

from external_user.models import ExternalUser
from organization.models import Organization


class ExternalUserSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(ExternalUser, on_delete=models.CASCADE)
    topic = models.CharField(max_length=255)


class ExternalUserSubscriptionCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_subscription = models.ForeignKey(
        ExternalUserSubscription, related_name="categories", on_delete=models.CASCADE
    )
    slug = models.SlugField()
    description = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)
