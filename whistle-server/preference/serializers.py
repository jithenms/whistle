import logging

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from sendgrid.helpers.mail import category

from external_user.models import ExternalUser
from preference.models import (
    ExternalUserPreferenceChannel,
    ExternalUserPreference,
    ChannelChoices,
)


class ExternalUserPreferenceChannelSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(max_length=255)

    class Meta:
        model = ExternalUserPreferenceChannel
        fields = ["id", "slug", "enabled"]

    def validate_slug(self, value):
        # Convert input to uppercase
        value_upper = value.upper()
        # Check if the value is a valid choice
        if value_upper not in ChannelChoices.values:
            raise serializers.ValidationError(f"'{value}' is not a valid choice.")
        return value_upper


class ExternalUserPreferenceSerializer(serializers.ModelSerializer):
    channels = ExternalUserPreferenceChannelSerializer(many=True)

    class Meta:
        model = ExternalUserPreference
        fields = ["id", "slug", "channels"]

    def create(self, validated_data):
        org = self.context["request"].user
        external_id = self.context.get("external_id")
        try:
            with transaction.atomic():
                channels_data = validated_data.pop("channels", [])
                external_user = ExternalUser.objects.get(external_id=external_id)

                user_preference = ExternalUserPreference.objects.create(
                    organization=org, user=external_user, slug=validated_data["slug"]
                )

                default_channels = [
                    {"slug": "web", "enabled": True},
                    {"slug": "email", "enabled": True},
                    {"slug": "sms", "enabled": True},
                ]

                for channel in channels_data:
                    for default_channel in default_channels:
                        if channel["slug"] == default_channel["slug"]:
                            default_channel.update(channel)

                for channel in default_channels:
                    ExternalUserPreferenceChannel.objects.create(
                        user_preference=user_preference, **channel
                    )

                logging.info(
                    "Preference with id: %s created for user: %s in org: %s",
                    user_preference.id,
                    external_user.id,
                    org.id,
                )

                return user_preference
        except ExternalUser.DoesNotExist:
            logging.error(
                "Invalid external id: %s provided for org: %s while creating preference",
                external_id,
                org.id,
            )
            raise ValidationError(
                "Invalid External Id. Please provide a valid External Id in the request header.",
                "invalid_external_id",
            )

    def update(self, instance, validated_data, **kwargs):
        org = self.context["request"].user
        external_id = self.context.get("external_id")
        with transaction.atomic():
            channels_data = validated_data.pop("channels", [])
            instance.slug = validated_data.get("slug", instance.slug)
            instance.save()

            if self.partial:
                for channel in channels_data:
                    ExternalUserPreferenceChannel.objects.update_or_create(
                        user_preference=instance,
                        slug=channel.get("slug"),
                        defaults={"enabled": channel.get("enabled")},
                    )
            else:
                ExternalUserPreferenceChannel.objects.filter(
                    user_preference=instance
                ).delete()
                for channel in channels_data:
                    ExternalUserPreferenceChannel.objects.create(
                        user_preference=instance, **channel
                    )

            logging.info(
                "Preference with id: %s updated for user: %s in org: %s",
                instance.id,
                instance.user.id,
                org.id,
            )

            return instance
