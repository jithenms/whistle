from rest_framework import serializers

from authn.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug']
        read_only_fields = ('name', 'slug')

