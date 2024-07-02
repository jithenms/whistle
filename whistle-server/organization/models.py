import uuid

from django.db import models


class Organization(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    clerk_org_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    api_key_encrypt = models.CharField(max_length=255, unique=True)
    api_key_hash = models.CharField(max_length=255, unique=True)
    api_secret_encrypt = models.CharField(max_length=255, unique=True)
    api_secret_hash = models.CharField(max_length=255, unique=True)
    api_secret_salt = models.CharField(max_length=255, unique=True)


class OrganizationUser(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="auth_users")
    clerk_user_id = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    primary_email = models.CharField(max_length=255, unique=True)