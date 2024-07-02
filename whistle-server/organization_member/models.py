import uuid
from django.db import models
from organization.models import Organization
from account.models import Account


# Create your models here.
class OrganizationMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
