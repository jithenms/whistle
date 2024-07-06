import logging

from rest_framework import serializers

from external_user.models import (
    ExternalUser,
)


class ExternalUserSerializer(serializers.ModelSerializer):
    external_id = serializers.CharField(max_length=255, required=False)
    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False)
    email = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=255, required=False)

    class Meta:
        model = ExternalUser
        fields = ["id", "external_id", "first_name", "last_name", "email", "phone"]

    def create(self, validated_data):
        org = self.context["request"].user
        validated_data["organization"] = org
        response = super().create(validated_data)
        logging.info("External user with id: %s created for org: %s", response.id, org.id)
        return response

    def update(self, instance, validated_data):
        org = self.context["request"].user
        response = super().update(instance, validated_data)
        logging.info("External user with id: %s updated for org: %s", instance.id, org.id)
        return response
