from rest_framework import serializers, permissions
from account.models import Account


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
