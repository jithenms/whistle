import uuid
from django.db import models


class Account(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    auth0_id = models.CharField(max_length=255, unique=True)
    nickname = models.CharField(max_length=255, null=True, blank=True)
    organization = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, unique=True)
    api_key_encrypt = models.CharField(max_length=255, unique=True)
    api_key_hash = models.CharField(max_length=255, unique=True)
    api_secret_encrypt = models.CharField(max_length=255, unique=True)
    api_secret_hash = models.CharField(max_length=255, unique=True)
    api_secret_salt = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
