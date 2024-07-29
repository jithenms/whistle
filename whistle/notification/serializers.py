import logging

from rest_framework import serializers

from audience.models import Audience
from connector.models import Sendgrid, Twilio, FCM, APNS
from external_user.models import ExternalUser
from external_user.serializers import ExternalUserSerializer
from notification.models import (
    Notification,
    Broadcast,
)


class InAppSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    content = serializers.CharField(required=False)
    enabled = serializers.BooleanField(default=False)


class EmailSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    content = serializers.CharField(required=False)
    sendgrid_template_id = serializers.CharField(required=False)
    enabled = serializers.BooleanField(default=False)


class SMSSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    content = serializers.CharField(required=False)
    enabled = serializers.BooleanField(default=False)


class PushSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    content = serializers.CharField(required=False)
    badge = serializers.CharField(required=False)
    sound = serializers.CharField(required=False)
    enabled = serializers.BooleanField(default=False)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "broadcast_id",
            "recipient_id",
            "title",
            "content",
            "action_link",
            "channel",
            "status",
            "error_reason",
            "metadata",
            "sent_at",
            "seen_at",
            "read_at",
            "clicked_at",
            "archived_at",
        ]
        read_only_fields = (
            "broadcast_id",
            "recipient_id",
            "sent_at",
            "channel",
            "status",
            "error_reason",
        )

    def update(self, instance, validated_data):
        for field in [
            "channel",
            "external_id",
            "title",
            "content",
            "action_link",
            "status",
            "error_reason",
        ]:
            if field in validated_data:
                validated_data.pop(field)
        return super().update(instance, validated_data)


class BroadcastChannelSerializer(serializers.Serializer):
    in_app = InAppSerializer(required=False, default=InAppSerializer().data)
    email = EmailSerializer(required=False, default=EmailSerializer().data)
    sms = SMSSerializer(required=False, default=SMSSerializer().data)
    push = PushSerializer(required=False, default=PushSerializer().data)


class BroadcastRecipientSerializer(serializers.ModelSerializer):
    external_id = serializers.CharField(required=False)
    email = serializers.CharField(required=False)

    class Meta:
        model = ExternalUser
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
    title = serializers.CharField(write_only=True)
    content = serializers.CharField(write_only=True)
    action_link = serializers.CharField(required=False, write_only=True)
    audience_id = serializers.UUIDField(required=False, write_only=True)
    recipients = BroadcastRecipientSerializer(many=True)
    channels = BroadcastChannelSerializer(write_only=True)
    merge_tags = serializers.JSONField(required=False, write_only=True, default=dict)

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
            "recipients",
            "merge_tags",
            "metadata",
            "additional_info",
            "status",
        ]
        read_only_fields = ("status", "metadata")

    def validate(self, data):
        if not data.get("recipients", []) and "audience_id" not in data:
            raise serializers.ValidationError(
                "'recipients' or 'audience_id' not provided. Please provide either 'recipients' or an 'audience_id'.",
                "recipients_or_audience_id_not_provided",
            )

        if "audience_id" in data:
            try:
                Audience.objects.get(
                    organization=self.context["request"].user,
                    pk=data["audience_id"],
                )
            except Audience.DoesNotExist:
                logging.error(
                    "Invalid audience id: %s provided for org: %s",
                    data["audience_id"],
                    self.context["request"].user.id,
                )
                raise serializers.ValidationError(
                    "Audience not found. Please provide a valid Audience ID.",
                    "invalid_audience_id",
                )

        if data["channels"]["email"]["enabled"]:
            sendgrid = Sendgrid.objects.filter(
                organization=self.context["request"].user
            )
            if not sendgrid:
                raise serializers.ValidationError(
                    "Sendgrid account not configured. Please configure a Sendgrid account to send emails.",
                    "sendgrid_account_not_configured",
                )

        if data["channels"]["sms"]["enabled"]:
            twilio = Twilio.objects.filter(organization=self.context["request"].user)
            if not twilio:
                raise serializers.ValidationError(
                    "Twilio account not configured. Please configure a Twilio account to send texts.",
                    "twilio_account_not_configured",
                )

        if data["channels"]["push"]["enabled"]:
            fcm = FCM.objects.filter(organization=self.context["request"].user)
            apns = APNS.objects.filter(organization=self.context["request"].user)

            if not fcm and not apns:
                raise serializers.ValidationError(
                    "FCM and APNS are not configured. Please configure at least one to send mobile notifications.",
                    "fcm_and_apns_not_configured",
                )

        if data["merge_tags"] and "email" not in data.get("channels", {}):
            raise serializers.ValidationError(
                {
                    "merge_tags": "The 'merge_tags' field requires 'channels.email.sendgrid_template_id' to be "
                    "specified."
                },
                "sendgrid_template_id_unspecified",
            )

        return super().validate(data)

    def create(self, validated_data, **kwargs):
        org = self.context["request"].user
        validated_data["organization"] = org

        for field in [
            "recipients",
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
