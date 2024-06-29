from rest_framework import serializers

from account.models import Account


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'auth0_id', 'nickname', 'organization', 'email']
        extra_kwargs = {
            'auth0_id': {'write_only': True},
        }
