from django.db import models
import uuid

from user.models import User


class Credential(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    secret_prefix = models.CharField(max_length=255)
    secret_hash = models.CharField(max_length=255)
    salt = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CredentialScope(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    credential_id = models.ForeignKey(Credential, on_delete=models.CASCADE)
    scope = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)