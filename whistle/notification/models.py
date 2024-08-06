import uuid

from django.db import models

from external_user.models import ExternalUser
from organization.models import Organization
from preference.models import ChannelChoices


class BroadcastStatusChoices(models.TextChoices):
    SCHEDULED = "SCHEDULED", "SCHEDULED"
    QUEUED = "QUEUED", "QUEUED"
    PROCESSED = "PROCESSED", "PROCESSED"
    FAILED = "FAILED", "FAILED"


class Broadcast(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_id = models.UUIDField(unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    category = models.SlugField(null=True)
    topic = models.CharField(null=True)
    title = models.CharField()
    content = models.CharField()
    action_link = models.CharField(null=True)
    additional_info = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    schedule_at = models.DateTimeField(null=True)
    status = models.CharField(choices=BroadcastStatusChoices.choices)
    sent_at = models.DateTimeField(null=True)


class NotificationStatusChoices(models.TextChoices):
    QUEUED = "QUEUED", "QUEUED"
    PROCESSED = "PROCESSED", "PROCESSED"
    FAILED = "FAILED", "FAILED"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    broadcast = models.ForeignKey(Broadcast, on_delete=models.PROTECT)
    recipient = models.ForeignKey(ExternalUser, on_delete=models.PROTECT)
    status = models.CharField(choices=NotificationStatusChoices.choices)
    clicked_at = models.DateTimeField(null=True)
    seen_at = models.DateTimeField(null=True)
    read_at = models.DateTimeField(null=True)
    archived_at = models.DateTimeField(null=True)


class DeliveryStatusChoices(models.TextChoices):
    DELIVERED = "DELIVERED", "DELIVERED"
    ATTEMPTED = "ATTEMPTED", "ATTEMPTED"
    UNDELIVERED = "UNDELIVERED", "UNDELIVERED"
    NOT_SENT = "NOT_SENT", "NOT_SENT"


class NotificationDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.PROTECT, related_name="deliveries"
    )
    channel = models.CharField(choices=ChannelChoices.choices)
    title = models.CharField(null=True, blank=True)
    content = models.CharField(null=True, blank=True)
    action_link = models.CharField(null=True, blank=True)
    status = models.CharField(choices=DeliveryStatusChoices.choices)
    error_reason = models.CharField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True)
