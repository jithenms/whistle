import logging

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from connector.models import Twilio, Sendgrid, APNS, FCM


class TwilioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Twilio
        fields = ["id", "from_phone", "account_sid", "auth_token"]

    def create(self, validated_data):
        org = self.context["request"].user
        validated_data["organization"] = org

        twilio_conn = Twilio.objects.filter(organization=org)

        if twilio_conn:
            raise ValidationError(
                "A Twilio account is already connected to your organization.",
                "twilio_connection_exists",
            )

        response = super().create(validated_data)

        logging.info(
            "Twilio connection with id: %s created for org: %s", response.id, org.id
        )

        return response


class SendgridSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sendgrid
        fields = ["id", "from_email", "api_key"]

    def create(self, validated_data):
        org = self.context["request"].user
        validated_data["organization"] = org

        sendgrid_conn = Sendgrid.objects.filter(organization=org)

        if sendgrid_conn:
            raise ValidationError(
                "A Sendgrid account is already connected to your organization.",
                "sendgrid_connection_exists",
            )

        response = super().create(validated_data)

        logging.info(
            "Sendgrid connection with id: %s created for org: %s", response.id, org.id
        )

        return response


class APNSSerializer(serializers.ModelSerializer):
    class Meta:
        model = APNS
        fields = ["id", "key_p8", "key_id", "team_id", "use_sandbox"]

    def create(self, validated_data):
        org = self.context["request"].user
        validated_data["organization"] = org

        apple_conn = APNS.objects.filter(organization=org)

        if apple_conn:
            raise ValidationError(
                "An Apple Push Notification Service account is already connected to your organization.",
                "apple_connection_exists",
            )

        response = super().create(validated_data)

        logging.info(
            "Apple Push Notification Service connection with id: %s created for org: %s",
            response.id,
            org.id,
        )

        return response


class FCMSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCM
        fields = ["id", "credentials", "project_id"]

    def create(self, validated_data):
        org = self.context["request"].user
        validated_data["organization"] = org

        fcm_conn = FCM.objects.filter(organization=org)

        if fcm_conn:
            raise ValidationError(
                "A Firebase Cloud Messaging project is already connected to your organization.",
                "fcm_connection_exists",
            )

        response = super().create(validated_data)

        logging.info(
            "Firebase Cloud Messaging connection with id: %s created for org: %s",
            response.id,
            org.id,
        )

        return response
