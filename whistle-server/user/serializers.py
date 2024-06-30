from rest_framework import serializers

from user.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['external_id', 'first_name', 'last_name', 'email', 'phone']

    def create(self, validated_data):
        validated_data['account'] = self.context['request'].user
        return super().create(validated_data)