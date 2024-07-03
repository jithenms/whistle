import uuid

from django.db import models

from organization.models import Organization


class ExternalUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255)
    phone = models.CharField(max_length=255, null=True, blank=True)


class ExternalUserPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(ExternalUser, on_delete=models.CASCADE)
    slug = models.SlugField()


CHANNELS = (("web", "web"), ("email", "email"), ("sms", "sms"))


class ExternalUserPreferenceChannel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_preference = models.ForeignKey(
        ExternalUserPreference, related_name="channels", on_delete=models.CASCADE
    )
    slug = models.SlugField(choices=CHANNELS)
    enabled = models.BooleanField(default=False)


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
