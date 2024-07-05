import logging

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

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
        for field in [
            "channels",
            "external_id",
            "category",
            "topic",
            "title",
            "content",
            "action_link",
        ]:
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
        logging.info(validated_data)
        delivered_to = self.context["delivered_to"]
        validated_data.pop("recipients")
        validated_data.pop("channels")

        batch_notification = BatchNotification(
            **validated_data, organization_id=self.context["org_id"]
        )
        batch_notification.save()

        for recipient_id in delivered_to:
            try:
                external_user = ExternalUser.objects.get(pk=recipient_id)
                batch_notification.recipients.add(external_user)
            except ExternalUser.DoesNotExist:
                logging.error(
                    "External user: %s in delivered to set for notification batch: %s does not exist in db",
                    recipient_id,
                    validated_data["id"],
                )
                raise ValidationError(
                    f"External user: {recipient_id} in delivered to set for notification batch: {validated_data['id']}"
                    f" does not exist in db",
                    "external_user_not_found",
                )

        return batch_notification
