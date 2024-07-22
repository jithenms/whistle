import uuid

from django.db import models

from external_user.models import ExternalUser
from organization.models import Organization
from preference.models import ChannelChoices


class Broadcast(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    category = models.SlugField(null=True, blank=True)
    topic = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255)
    content = models.CharField(max_length=255)
    action_link = models.CharField(max_length=255, blank=True)
    additional_info = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=255)
    sent_at = models.DateTimeField(null=True, blank=True)


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    recipient = models.ForeignKey(ExternalUser, on_delete=models.PROTECT)
    broadcast = models.ForeignKey(Broadcast, on_delete=models.PROTECT)
    category = models.SlugField(null=True, blank=True)
    topic = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255)
    content = models.CharField(max_length=255)
    action_link = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)


class NotificationChannel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    slug = models.SlugField(choices=ChannelChoices.choices)
    status = models.CharField(max_length=255)
    reason = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(null=True, blank=True)
