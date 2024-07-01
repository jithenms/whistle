import uuid
from django.db import models

from authn.models import Organization
from user.models import User

status = (
    'delivered', 'delivered',
    'failed', 'failed'
)


class Notification(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    recipient = models.ForeignKey(User, on_delete=models.PROTECT)
    category = models.SlugField(null=True, blank=True)
    topic = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.CharField(max_length=255)
    action_link = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255)
    sent_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
