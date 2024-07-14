from rest_framework import serializers

from external_user.serializers import ExternalUserSerializer
from notification.models import (
    Notification,
    Broadcast,
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
    additional_info = serializers.JSONField(required=False)

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
            "content",
            "action_link",
            "additional_info",
            "sent_at",
            "seen_at",
            "read_at",
            "archived_at",
        ]
        read_only_fields = ("recipient", "sent_at")

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


class BroadcastSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField()
    recipients = ExternalUserSerializer(many=True)
    channels = NotificationChannelsSerializer(required=False)
    additional_info = serializers.JSONField(required=False)

    class Meta:
        model = Broadcast
        fields = [
            "id",
            "recipients",
            "category",
            "topic",
            "channels",
            "title",
            "content",
            "action_link",
            "additional_info",
            "status",
        ]
        read_only_fields = ("status",)

    def create(self, validated_data, **kwargs):
        org = self.context["request"].user
        validated_data["organization"] = org
        validated_data.pop("recipients")
        if "channels" in validated_data:
            validated_data.pop("channels")
        instance = Broadcast(**validated_data, **kwargs)
        instance.save()
        return instance
