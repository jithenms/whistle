from rest_framework import serializers

from audience.models import Audience
from external_user.models import ExternalUser
from external_user.serializers import ExternalUserSerializer
from notification.models import (
    Notification,
    Broadcast,
    NotificationDelivery,
)
from preference.models import ChannelChoices
from provider.models import Provider, ProviderTypeChoices


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = [
            "title",
            "content",
            "action_link",
            "channel",
            "status",
            "error_reason",
            "metadata",
            "sent_at",
        ]
        read_only_fields = (
            "title",
            "content",
            "action_link",
            "channel",
            "status",
            "error_reason",
            "metadata",
            "sent_at",
        )


class NotificationSerializer(serializers.ModelSerializer):
    deliveries = NotificationDeliverySerializer(read_only=True, many=True)
    recipient = ExternalUserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "broadcast_id",
            "recipient",
            "deliveries",
            "seen_at",
            "read_at",
            "clicked_at",
            "archived_at",
        ]
        read_only_fields = ("broadcast", "recipient", "deliveries")


class APNSProviderSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    subtitle = serializers.CharField(required=False)
    body = serializers.CharField(required=False)
    badge = serializers.IntegerField(required=False)
    sound = serializers.CharField(required=False)


class FCMProviderSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    body = serializers.CharField(required=False)


class SendgridProviderSerializer(serializers.Serializer):
    sg_template_id = serializers.CharField(required=False)
    subject = serializers.CharField(required=False)
    content = serializers.CharField(required=False)


class TwilioProviderSerializer(serializers.Serializer):
    body = serializers.CharField(required=False)


class BroadcastProvidersSerializer(serializers.Serializer):
    twilio = TwilioProviderSerializer(required=False)
    sendgrid = SendgridProviderSerializer(required=False)
    apns = APNSProviderSerializer(required=False)
    fcm = FCMProviderSerializer(required=False)


class BroadcastRecipientSerializer(serializers.Serializer):
    external_id = serializers.CharField(required=False)
    email = serializers.CharField(required=False)

    class Meta:
        fields = [
            "external_id",
            "first_name",
            "last_name",
            "email",
            "phone",
        ]

    def validate(self, data):
        if "email" not in data and "external_id" not in data:
            raise serializers.ValidationError(
                "'email' or 'external_id' not provided for a recipient. Please provide either an 'email' or "
                "'external_id' for this recipient.",
                "email_or_external_id_not_provided",
            )
        return data


class BroadcastSerializer(serializers.ModelSerializer):
    title = serializers.CharField()
    content = serializers.CharField()
    action_link = serializers.CharField(required=False)
    audience_id = serializers.UUIDField(required=False)
    recipients = BroadcastRecipientSerializer(write_only=True, many=True)
    channels = serializers.ListSerializer(
        child=serializers.CharField(), write_only=True
    )
    merge_tags = serializers.JSONField(required=False, write_only=True, default=dict)
    providers = BroadcastProvidersSerializer(required=False, write_only=True)

    class Meta:
        model = Broadcast
        fields = [
            "id",
            "schedule_at",
            "audience_id",
            "category",
            "topic",
            "channels",
            "title",
            "content",
            "action_link",
            "providers",
            "recipients",
            "merge_tags",
            "metadata",
            "additional_info",
            "status",
        ]
        read_only_fields = ("status", "metadata")

    def validate_channels(self, channels):
        if not channels:
            raise serializers.ValidationError(
                "The 'channels' field is empty. Please provide at least one delivery channel.",
                "channels_not_provided",
            )

        values = []
        for value in channels:
            value_upper = value.upper()
            if value_upper not in ChannelChoices.values:
                raise serializers.ValidationError(
                    f"'{value}' is not a valid 'slug'.", "invalid_slug"
                )
            values.append(value_upper)
        return values

    def validate(self, data):
        if not data.get("recipients", []) and "audience_id" not in data:
            raise serializers.ValidationError(
                "'recipients' or 'audience_id' not provided. Please provide either 'recipients' or an 'audience_id'.",
                "recipients_or_audience_id_not_provided",
            )

        if ProviderTypeChoices.EMAIL.value in data["channels"]:
            providers = Provider.objects.filter(
                organization=self.context["request"].user,
                provider_type=ProviderTypeChoices.EMAIL,
                enabled=True,
            ).count()
            if providers == 0:
                raise serializers.ValidationError(
                    {
                        "channels": "No email providers configured or enabled. Please configure an email provider"
                        " to send emails."
                    },
                    "email_providers_not_configured",
                )

        if ProviderTypeChoices.PUSH.value in data["channels"]:
            providers = Provider.objects.filter(
                organization=self.context["request"].user,
                provider_type=ProviderTypeChoices.PUSH,
                enabled=True,
            ).count()
            if providers == 0:
                raise serializers.ValidationError(
                    {
                        "channels": "No push providers configured or enabled. Please configure a push provider"
                        " to send push notifications."
                    },
                    "push_providers_not_configured",
                )

        if ProviderTypeChoices.SMS.value in data["channels"]:
            providers = Provider.objects.filter(
                organization=self.context["request"].user,
                provider_type=ProviderTypeChoices.SMS,
                enabled=True,
            ).count()
            if providers == 0:
                raise serializers.ValidationError(
                    {
                        "channels": "No SMS providers configured or enabled. Please configure an SMS provider"
                        " to send texts."
                    },
                    "sms_providers_not_configured",
                )

        if "audience_id" in data:
            try:
                Audience.objects.get(
                    organization=self.context["request"].user,
                    pk=data["audience_id"],
                )
            except Audience.DoesNotExist:
                raise serializers.ValidationError(
                    "Audience not found. Please provide a valid Audience ID.",
                    "invalid_audience_id",
                )

        return super().validate(data)

    def create(self, validated_data, **kwargs):
        org = self.context["request"].user
        validated_data["organization"] = org

        for field in [
            "channels",
            "filters",
            "audience_id",
            "schedule_at",
            "merge_tags",
        ]:
            if field in validated_data:
                validated_data.pop(field)

        instance = Broadcast(**validated_data, **kwargs)
        instance.save()
        return instance


class NotificationStatusSerializer(serializers.Serializer):
    pass
