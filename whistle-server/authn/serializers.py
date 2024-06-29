from rest_framework import serializers

from authn.models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['id', 'api_key', 'api_secret_hint']
        read_only_fields = ('api_key', 'api_secret_hint')
