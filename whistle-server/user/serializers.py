from rest_framework import serializers

from user.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'auth0_id', 'nickname', 'organization', 'email']
        extra_kwargs = {
            'auth0_id': {'write_only': True},
        }
