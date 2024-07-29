from django.db import transaction
from rest_framework import serializers

from provider.models import (
    Provider,
    ProviderChoices,
    ProviderTypeChoices,
    ProviderCredential,
)


class SendgridSerializer(serializers.ModelSerializer):
    from_email = serializers.CharField()
    api_key = serializers.CharField()
    enabled = serializers.BooleanField()

    class Meta:
        model = Provider
        fields = ["id", "api_key", "from_email", "enabled"]

    @transaction.atomic
    def create(self, validated_data):
        provider = Provider.objects.create(
            organization=self.context["request"].user,
            provider_type=ProviderTypeChoices.EMAIL,
            provider=ProviderChoices.SENDGRID,
            enabled=validated_data["enabled"],
        )

        ProviderCredential.objects.create(
            provider=provider, slug="from_email", value=validated_data["from_email"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="api_key", value=validated_data["api_key"]
        )

        return provider

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.enabled = validated_data.get("enabled", instance.enabled)
        instance.save()

        credentials = {
            "from_email": validated_data.get("from_email"),
            "api_key": validated_data.get("api_key"),
        }

        for slug, value in credentials.items():
            if value is not None:
                credential, created = ProviderCredential.objects.get_or_create(
                    provider=instance, slug=slug
                )
                credential.value = value
                credential.save()

        return instance

    def delete(self, instance):
        instance.credentials.all().delete()
        instance.delete()

    def to_representation(self, instance):
        representation = {"id": instance.id, "enabled": instance.enabled}
        for credential in instance.credentials.iterator():
            if credential.slug == "from_email":
                representation["from_email"] = credential.value
            elif credential.slug == "api_key":
                representation["api_key"] = credential.value
        return representation


class TwilioSerializer(serializers.ModelSerializer):
    from_phone = serializers.CharField()
    account_sid = serializers.CharField()
    auth_token = serializers.CharField()
    enabled = serializers.BooleanField()

    class Meta:
        model = Provider
        fields = ["id", "from_phone", "account_sid", "auth_token", "enabled"]

    @transaction.atomic
    def create(self, validated_data):
        provider = Provider.objects.create(
            organization=self.context["request"].user,
            provider_type=ProviderTypeChoices.SMS,
            provider=ProviderChoices.TWILIO,
            enabled=validated_data["enabled"],
        )

        ProviderCredential.objects.create(
            provider=provider, slug="from_phone", value=validated_data["from_phone"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="account_sid", value=validated_data["account_sid"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="auth_token", value=validated_data["auth_token"]
        )

        return provider

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.enabled = validated_data.get("enabled", instance.enabled)
        instance.save()

        credentials = {
            "from_phone": validated_data.get("from_phone"),
            "account_sid": validated_data.get("account_sid"),
            "auth_token": validated_data.get("auth_token"),
        }

        for slug, value in credentials.items():
            if value is not None:
                credential, created = ProviderCredential.objects.get_or_create(
                    provider=instance, slug=slug
                )
                credential.value = value
                credential.save()

        return instance

    def delete(self, instance):
        instance.credentials.all().delete()
        instance.delete()

    def to_representation(self, instance):
        representation = {"id": instance.id, "enabled": instance.enabled}
        for credential in instance.credentials.iterator():
            if credential.slug == "from_phone":
                representation["from_phone"] = credential.value
            elif credential.slug == "account_sid":
                representation["account_sid"] = credential.value
            elif credential.slug == "auth_token":
                representation["auth_token"] = credential.value
        return representation


class APNSSerializer(serializers.ModelSerializer):
    key_p8 = serializers.CharField()
    key_id = serializers.CharField()
    team_id = serializers.CharField()
    bundle_id = serializers.CharField()
    use_sandbox = serializers.BooleanField()
    enabled = serializers.BooleanField()

    class Meta:
        model = Provider
        fields = [
            "id",
            "key_p8",
            "key_id",
            "team_id",
            "bundle_id",
            "use_sandbox",
            "enabled",
        ]

    @transaction.atomic
    def create(self, validated_data):
        provider = Provider.objects.create(
            organization=self.context["request"].user,
            provider_type=ProviderTypeChoices.PUSH,
            provider=ProviderChoices.APNS,
            enabled=validated_data["enabled"],
        )

        ProviderCredential.objects.create(
            provider=provider, slug="key_p8", value=validated_data["key_p8"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="key_id", value=validated_data["key_id"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="team_id", value=validated_data["team_id"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="bundle_id", value=validated_data["bundle_id"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="use_sandbox", value=validated_data["use_sandbox"]
        )

        return provider

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.enabled = validated_data.get("enabled", instance.enabled)
        instance.save()

        credentials = {
            "key_p8": validated_data.get("key_p8"),
            "key_id": validated_data.get("key_id"),
            "team_id": validated_data.get("team_id"),
            "bundle_id": validated_data.get("bundle_id"),
            "use_sandbox": validated_data.get("use_sandbox"),
        }

        for slug, value in credentials.items():
            if value is not None:
                credential, created = ProviderCredential.objects.get_or_create(
                    provider=instance, slug=slug
                )
                credential.value = value
                credential.save()

        return instance

    def delete(self, instance):
        instance.credentials.all().delete()
        instance.delete()

    def to_representation(self, instance):
        representation = {"id": instance.id, "enabled": instance.enabled}
        for credential in instance.credentials.iterator():
            if credential.slug == "key_p8":
                representation["key_p8"] = credential.value
            elif credential.slug == "key_id":
                representation["key_id"] = credential.value
            elif credential.slug == "team_id":
                representation["team_id"] = credential.value
            elif credential.slug == "use_sandbox":
                representation["use_sandbox"] = credential.value
        return representation


class FCMSerializer(serializers.ModelSerializer):
    credentials = serializers.CharField()
    project_id = serializers.CharField()
    enabled = serializers.BooleanField()

    class Meta:
        model = Provider
        fields = [
            "id",
            "credentials",
            "project_id",
            "enabled",
        ]

    @transaction.atomic
    def create(self, validated_data):
        provider = Provider.objects.create(
            organization=self.context["request"].user,
            provider_type=ProviderTypeChoices.PUSH,
            provider=ProviderChoices.FCM,
            enabled=validated_data["enabled"],
        )

        ProviderCredential.objects.create(
            provider=provider, slug="credentials", value=validated_data["credentials"]
        )
        ProviderCredential.objects.create(
            provider=provider, slug="project_id", value=validated_data["project_id"]
        )

        return provider

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.enabled = validated_data.get("enabled", instance.enabled)
        instance.save()

        credentials = {
            "credentials": validated_data.get("credentials"),
            "project_id": validated_data.get("project_id"),
        }

        for slug, value in credentials.items():
            if value is not None:
                credential, created = ProviderCredential.objects.get_or_create(
                    provider=instance, slug=slug
                )
                credential.value = value
                credential.save()

        return instance

    def delete(self, instance):
        instance.credentials.all().delete()
        instance.delete()

    def to_representation(self, instance):
        representation = {"id": instance.id, "enabled": instance.enabled}
        for credential in instance.credentials.iterator():
            if credential.slug == "credentials":
                representation["credentials"] = credential.value
            elif credential.slug == "project_id":
                representation["project_id"] = credential.value
        return representation
