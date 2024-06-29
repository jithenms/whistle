from rest_framework import serializers

from authn.models import Credential


class CredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credential
        fields = ['id', 'api_key', 'api_secret_hint']
        read_only_fields = ('api_key', 'api_secret_hint')
