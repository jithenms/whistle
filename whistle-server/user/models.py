import uuid
from django.db import models

from authn.models import Organization


class User(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255)
    phone = models.CharField(max_length=255, null=True, blank=True)


class UserPreference(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    slug = models.SlugField()


CHANNELS = (
    ('web', 'web'),
    ('email', 'email'),
    ('sms', 'sms')
)


class UserPreferenceChannel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    user_preference = models.ForeignKey(UserPreference, related_name='channels', on_delete=models.CASCADE)
    slug = models.SlugField(choices=CHANNELS)
    enabled = models.BooleanField(default=False)


class UserSubscription(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=255)


class UserSubscriptionCategory(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    user_subscription = models.ForeignKey(UserSubscription, related_name='categories', on_delete=models.CASCADE)
    slug = models.SlugField()
    description = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)
