import uuid

from django.db import models

from organization.models import Organization


class Twilio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    from_phone = models.CharField(unique=True)
    account_sid = models.CharField(unique=True)
    auth_token = models.CharField(unique=True)


class Sendgrid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    from_email = models.CharField(unique=True)
    api_key = models.CharField(unique=True)


class APNS(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    key_p8 = models.TextField()
    key_id = models.CharField(unique=True)
    team_id = models.CharField()
    use_sandbox = models.BooleanField(default=False)


class FCM(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    credentials = models.TextField()
    project_id = models.CharField(unique=True)
