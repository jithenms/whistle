import logging

from rest_framework import serializers

from external_user.models import (
    ExternalUser,
    ExternalUserDevice,
    PlatformChoices,
)


class ExternalUserSerializer(serializers.ModelSerializer):
    external_id = serializers.CharField(max_length=255, required=False)
    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False)
    email = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=255, required=False)
    metadata = serializers.JSONField(required=False)

    class Meta:
        model = ExternalUser
        fields = [
            "id",
            "external_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "metadata",
        ]

    def create(self, validated_data):
        org = self.context["request"].user
        validated_data["organization"] = org
        response = super().create(validated_data)
        logging.info(
            "External user with id: %s created for org: %s", response.id, org.id
        )
        return response

    def update(self, instance, validated_data):
        org = self.context["request"].user
        response = super().update(instance, validated_data)
        logging.info(
            "External user with id: %s updated for org: %s", instance.id, org.id
        )
        return response

class ExternalUserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalUserDevice
        fields = [
            "id",
            "token",
            "platform",
        ]

    def validate_platform(self, value):
        # Convert input to uppercase
        value_upper = value.upper()
        # Check if the value is a valid choice
        if value_upper not in PlatformChoices.values:
            raise serializers.ValidationError(
                f"'{value}' is not a valid choice for 'platform'.", "invalid_platform"
            )
        return value_upper
