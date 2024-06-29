from django.db import models
import uuid

from account.models import Account


class Credential(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    api_key = models.CharField(max_length=255, unique=True)
    api_secret_hash = models.CharField(max_length=255, unique=True)
    api_secret_hint = models.CharField(max_length=255)
    salt = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# todo add scopes support
