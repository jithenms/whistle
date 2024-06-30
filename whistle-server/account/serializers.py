import os

from rest_framework import serializers

from account.models import Account


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'auth0_id', 'nickname', 'organization', 'email']
        read_only_fields = ('api_key_encrypt', 'api_key_hash', 'api_secret_encrypt', 'api_secret_hash', 'api_secret_salt')
        extra_kwargs = {
            'auth0_id': {'write_only': True},
        }
