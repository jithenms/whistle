import uuid
from django.db import models

from account.models import Account


class Twilio(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    from_phone = models.CharField(max_length=255, unique=True)
    account_sid = models.CharField(max_length=255, unique=True)
    auth_token = models.CharField(max_length=255, unique=True)


class Sendgrid(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    from_email = models.CharField(max_length=255, unique=True)
    api_key = models.CharField(max_length=255, unique=True)
