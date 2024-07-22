from rest_framework import serializers

from audience.serializers import FilterSerializer
from external_user.serializers import ExternalUserSerializer
from notification.models import (
    Notification,
    Broadcast,
)


class ChannelEmailSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255, required=False)
    content = serializers.CharField(max_length=255, required=False)
    sendgrid_template_id = serializers.CharField(max_length=255, required=False)

    def validate(self, data):
        subject = data.get('subject')
        content = data.get('content')
        sendgrid_template_id = data.get('sendgrid_template_id')

        if not sendgrid_template_id:
            if subject and not content:
                raise serializers.ValidationError(
                    {'content': "You must provide content for the email if using a subject."},
                    "missing_email_content"
                )
            if content and not subject:
                raise serializers.ValidationError(
                    {'subject': "You must provide a subject for the email if using content."},
                    "missing_email_subject"
                )
            if not subject and not content:
                raise serializers.ValidationError(
                    {
                        'sendgrid_template_id': "The 'sendgrid_template_id' field is required "
                                                "if both 'subject' and 'content' are not provided.",
                        'subject': "The 'subject' field is required if 'sendgrid_template_id' is not provided.",
                        'content': "The 'content' field is required if 'sendgrid_template_id' is not provided."
                    },
                    "invalid_email_params"
                )

        return data


class ChannelSMSSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=255)


class ChannelMobilePushSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    subtitle = serializers.CharField(max_length=255, required=False)
    body = serializers.CharField(max_length=255)
    badge = serializers.CharField(max_length=255, required=False)
    sound = serializers.CharField(max_length=255, required=False)


class NotificationChannelsSerializer(serializers.Serializer):
    email = ChannelEmailSerializer(required=False)
    sms = ChannelSMSSerializer(required=False)
    mobile_push = ChannelMobilePushSerializer(required=False)


class NotificationSerializer(serializers.ModelSerializer):
    recipient = ExternalUserSerializer(read_only=True)
    additional_info = serializers.JSONField(required=False, default=dict)

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
    recipients = ExternalUserSerializer(many=True, required=False)
    schedule_at = serializers.DateTimeField(required=False)
    audience_id = serializers.UUIDField(required=False, write_only=True)
    filters = FilterSerializer(many=True, required=False, write_only=True)
    channels = NotificationChannelsSerializer(required=False)
    additional_info = serializers.JSONField(required=False, default=dict)
    data = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = Broadcast
        fields = [
            "id",
            "recipients",
            "schedule_at",
            "audience_id",
            "data",
            "filters",
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

    def validate(self, data):
        if "audience_id" in data and "filters" in data:
            raise serializers.ValidationError(
                "Cannot use both 'audience_id' and 'filters' together. Please specify only one.",
                "audience_and_filters_unsupported",
            )

        if "audience_id" in data and "recipients" in data:
            raise serializers.ValidationError(
                "Cannot use both 'audience_id' and 'recipients' together. Please specify only one.",
                "audience_and_recipients_unsupported",
            )

        if "data" in data and "email" not in data.get("channels", {}):
            raise ValidationError(
                {'data': "The 'data' field requires 'channels.email.sendgrid_template_id' to be specified."},
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
            "data",
        ]:
            if field in validated_data:
                validated_data.pop(field)

        instance = Broadcast(**validated_data, **kwargs)
        instance.save()
        return instance
