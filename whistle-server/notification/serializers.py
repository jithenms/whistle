from rest_framework import serializers

from notification.models import Notification
from user.serializers import UserSerializer


class ChannelEmailSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    content = serializers.CharField(max_length=255)


class ChannelSMSSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=255)


class NotificationChannelsSerializer(serializers.Serializer):
    email = ChannelEmailSerializer(required=False)
    sms = ChannelSMSSerializer(required=False)


class NotificationSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)

    seen_at = serializers.DateTimeField(required=False)
    read_at = serializers.DateTimeField(required=False)
    archived_at = serializers.DateTimeField(required=False)

    channels = NotificationChannelsSerializer(required=False)

    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'category', 'topic', 'title', 'status', 'content', 'action_link',
                  'sent_at', 'seen_at', 'read_at', 'channels', 'archived_at']
        read_only_fields = ('recipient', 'sent_at', 'status')

    def update(self, instance, validated_data):
        for field in ['category', 'topic', 'title', 'content', 'action_link']:
            if field in validated_data:
                validated_data.pop(field)
        return super().update(instance, validated_data)
