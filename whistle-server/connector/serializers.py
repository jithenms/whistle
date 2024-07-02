from rest_framework import serializers

from connector.models import Twilio, Sendgrid


class TwilioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Twilio
        fields = ["id", "from_phone", "account_sid", "auth_token"]

    def create(self, validated_data):
        validated_data["organization"] = self.context["request"].user
        return super().create(validated_data)


class SendgridSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sendgrid
        fields = ["id", "from_email", "api_key"]

    def create(self, validated_data):
        validated_data["organization"] = self.context["request"].user
        return super().create(validated_data)
