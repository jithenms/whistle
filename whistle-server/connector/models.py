import uuid

from django.db import models

from organization.models import Organization


class Twilio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    from_phone = models.CharField(max_length=255, unique=True)
    account_sid = models.CharField(max_length=255, unique=True)
    auth_token = models.CharField(max_length=255, unique=True)


class Sendgrid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    from_email = models.CharField(max_length=255, unique=True)
    api_key = models.CharField(max_length=255, unique=True)
