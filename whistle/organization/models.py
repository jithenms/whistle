import uuid

from django.db import models

from user.models import User
from whistle import fields, utils


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clerk_org_id = models.TextField(unique=True)
    name = models.CharField()
    slug = models.SlugField(unique=True)


class OrganizationCredentials(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, primary_key=True
    )

    api_key = fields.EncryptedField(key_id="alias/APICredentials")
    api_key_hash = models.TextField(unique=True)

    api_secret = fields.EncryptedField(key_id="alias/APICredentials")
    api_secret_hash = models.TextField(unique=True)

    api_secret_salt = models.TextField(unique=True)

    def save(self, *args, **kwargs):
        if self.api_key:
            self.api_key_hash = utils.perform_hash(self.api_key)
        if self.api_secret:
            self.api_secret_hash = utils.perform_hash(
                self.api_secret, self.api_secret_salt
            )
        return super().save(*args, **kwargs)


class OrganizationMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    role = models.CharField()
