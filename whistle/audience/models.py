import uuid

from django.db import models

from organization.models import Organization


class Audience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)


class OperatorChoices(models.TextChoices):
    GT = "GT", "GT"
    LT = "LT", "LT"
    GTE = "GTE", "GTE"
    LTE = "LTE", "LTE"
    EQ = "EQ", "EQ"
    NEQ = "NEQ", "NEQ"
    CONTAINS = "CONTAINS", "CONTAINS"
    DOES_NOT_CONTAIN = "DOES_NOT_CONTAIN", "DOES_NOT_CONTAIN"


class Filter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audience = models.ForeignKey(
        Audience, on_delete=models.CASCADE, related_name="filters"
    )
    property = models.CharField(max_length=255)
    operator = models.CharField(choices=OperatorChoices.choices, max_length=255)
    value = models.CharField()

    class Meta:
        unique_together = [["audience", "property"]]
