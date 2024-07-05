import logging

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from connector.models import Twilio, Sendgrid


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

        logging.info("Twilio connection with id: %s created for org: %s", response.id, org.id)

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

        logging.info("Sendgrid connection with id: %s created for org: %s", response.id, org.id)

        return response
