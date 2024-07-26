from rest_framework import serializers

from organization.models import Organization, OrganizationCredentials


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug"]


class OrganizationCredentialsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCredentials
        fields = ["organization_id", "api_key", "api_secret"]
