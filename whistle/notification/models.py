import uuid

from django.db import models

from external_user.models import ExternalUser
from organization.models import Organization
from preference.models import ChannelChoices


class Broadcast(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    recipients = models.ManyToManyField(ExternalUser, through="BroadcastRecipient")
    category = models.SlugField(null=True)
    topic = models.CharField(null=True)
    title = models.CharField()
    content = models.CharField()
    action_link = models.CharField(null=True)
    additional_info = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    schedule_at = models.DateTimeField(null=True)
    status = models.CharField()
    sent_at = models.DateTimeField(null=True)


class BroadcastRecipient(models.Model):
    broadcast = models.ForeignKey(Broadcast, on_delete=models.CASCADE)
    recipient = models.ForeignKey(ExternalUser, on_delete=models.CASCADE)
    error_reason = models.CharField()

    class Meta:
        unique_together = ("broadcast", "recipient")


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    broadcast = models.ForeignKey(Broadcast, on_delete=models.PROTECT)
    recipient = models.ForeignKey(ExternalUser, on_delete=models.PROTECT)
    clicked_at = models.DateTimeField(null=True)
    seen_at = models.DateTimeField(null=True)
    read_at = models.DateTimeField(null=True)
    archived_at = models.DateTimeField(null=True)


class NotificationDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.PROTECT, related_name="deliveries"
    )
    channel = models.CharField(choices=ChannelChoices.choices)
    title = models.CharField(null=True, blank=True)
    content = models.CharField(null=True, blank=True)
    action_link = models.CharField(null=True, blank=True)
    status = models.CharField()
    error_reason = models.CharField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True)
