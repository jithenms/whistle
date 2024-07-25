import logging

from django.db import transaction
from rest_framework import serializers

from external_user.models import ExternalUser
from subscription.models import (
    ExternalUserSubscription,
    ExternalUserSubscriptionCategory,
)


class ExternalUserSubscriptionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalUserSubscriptionCategory
        fields = ["id", "slug", "description"]


class ExternalUserSubscriptionSerializer(serializers.ModelSerializer):
    categories = ExternalUserSubscriptionCategorySerializer(many=True)

    class Meta:
        model = ExternalUserSubscription
        fields = ["id", "topic", "categories"]

    def create(self, validated_data):
        org = self.context["request"].user
        external_id = self.context.get("external_id")
        try:
            with transaction.atomic():
                category_data = validated_data.pop("categories", [])
                external_user = ExternalUser.objects.get(external_id=external_id)
                user_subscription = ExternalUserSubscription.objects.create(
                    organization=org, user=external_user, topic=validated_data["topic"]
                )

                for cat in category_data:
                    ExternalUserSubscriptionCategory.objects.create(
                        user_subscription=user_subscription, **cat
                    )

                logging.info(
                    "Subscription with id: %s created for user: %s in org: %s",
                    user_subscription.id,
                    external_user.id,
                    org.id,
                )

                return user_subscription
        except ExternalUser.DoesNotExist:
            logging.error(
                "Invalid external id: %s provided for org: %s while creating subscription",
                external_id,
                self.request.user.id,
            )
            raise serializers.ValidationError(
                "Invalid External Id. Please provide a valid External Id in the request header.",
                "invalid_external_id",
            )

    def update(self, instance, validated_data, **kwargs):
        org = self.context["request"].user
        external_id = self.context.get("external_id")
        with transaction.atomic():
            category_data = validated_data.pop("categories", [])
            instance.slug = validated_data.get("slug", instance.slug)
            instance.save()

            if self.partial:
                for category in category_data:
                    ExternalUserSubscriptionCategory.objects.update_or_create(
                        user_subscription=instance,
                        slug=category.get("slug"),
                        defaults={"description": category.get("description")},
                    )
            else:
                ExternalUserSubscriptionCategory.objects.filter(
                    user_subscription=instance
                ).delete()
                for category in category_data:
                    ExternalUserSubscriptionCategory.objects.create(
                        user_preference=instance, **category
                    )

            logging.info(
                "Subscription with id: %s updated for user: %s in org: %s",
                instance.id,
                instance.user.id,
                org.id,
            )

            return instance
