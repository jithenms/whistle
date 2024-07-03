from rest_framework import serializers

from external_user.models import ExternalUser
from external_user.serializers import ExternalUserSerializer
from notification.models import (
    Notification,
    BatchNotification,
)


class ChannelEmailSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    content = serializers.CharField(max_length=255)


class ChannelSMSSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=255)


class NotificationChannelsSerializer(serializers.Serializer):
    email = ChannelEmailSerializer(required=False)
    sms = ChannelSMSSerializer(required=False)


class NotificationSerializer(serializers.ModelSerializer):
    recipient = ExternalUserSerializer(read_only=True)

    seen_at = serializers.DateTimeField(required=False)
    read_at = serializers.DateTimeField(required=False)
    archived_at = serializers.DateTimeField(required=False)

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "category",
            "topic",
            "title",
            "status",
            "content",
            "action_link",
            "sent_at",
            "seen_at",
            "read_at",
            "archived_at",
        ]
        read_only_fields = ("recipient", "sent_at", "status")

    def update(self, instance, validated_data):
        for field in ["category", "topic", "title", "content", "action_link"]:
            if field in validated_data:
                validated_data.pop(field)
        return super().update(instance, validated_data)


class BatchNotificationSerializer(serializers.ModelSerializer):
    recipients = ExternalUserSerializer(many=True)
    channels = NotificationChannelsSerializer(required=False)

    class Meta:
        model = BatchNotification
        fields = [
            "id",
            "recipients",
            "category",
            "topic",
            "channels",
            "title",
            "status",
            "content",
        ]
        read_only_fields = ("status",)

    def create(self, validated_data):
        recipients = validated_data["recipients"]
        del validated_data["recipients"]
        del validated_data["channels"]

        batch_notification = BatchNotification(**validated_data)
        batch_notification.save()

        for recipient in recipients:
            lookup_field = "external_id" if "external_id" in recipient else "email"
            batch_notification.recipients.add(
                ExternalUser.objects.get(**{lookup_field: recipient[lookup_field]})
            )

        return batch_notification
