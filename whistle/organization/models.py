import uuid

from django.db import models

from user.models import User
from whistle import fields, utils
from whistle.fields import EncryptedFieldTypeChoices


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clerk_org_id = models.CharField(unique=True)
    name = models.CharField()
    slug = models.SlugField(unique=True)


class OrganizationCredentials(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, primary_key=True
    )

    api_key = fields.EncryptedField(EncryptedFieldTypeChoices.API_CREDENTIALS)
    api_key_hash = models.CharField(unique=True)

    api_secret = fields.EncryptedField(EncryptedFieldTypeChoices.API_CREDENTIALS)
    api_secret_hash = models.CharField(unique=True)

    api_secret_salt = models.CharField(unique=True)

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
