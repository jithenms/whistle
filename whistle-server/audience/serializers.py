import logging

from django.db import transaction, DatabaseError
from rest_framework import serializers

from audience.models import Audience, Filter, OperatorChoices


class FilterSerializer(serializers.ModelSerializer):
    operator = serializers.CharField(max_length=255)

    class Meta:
        model = Filter
        fields = ["property", "operator", "value"]

    def validate_operator(self, value):
        # Convert input to uppercase
        value_upper = value.upper()
        # Check if the value is a valid choice
        if value_upper not in OperatorChoices.values:
            raise serializers.ValidationError(f"'{value}' is not a valid choice.")
        return value_upper


class AudienceSerializer(serializers.ModelSerializer):
    filters = FilterSerializer(many=True)

    class Meta:
        model = Audience
        fields = ["id", "name", "description", "filters"]

    def create(self, validated_data):
        org = self.context["request"].user
        try:
            with transaction.atomic():
                instance = Audience(
                    organization=org,
                    name=validated_data.get("name", ""),
                    description=validated_data.get("description", ""),
                )
                instance.save()
                for _filter in validated_data["filters"]:
                    Filter.objects.create(audience=instance, **_filter)
                logging.info(
                    "Audience with id: %s created for org: %s", instance.id, org.id
                )
                return instance
        except DatabaseError as error:
            logging.error(
                "Failed to create audience for org: %s with error: %s", org.id, error
            )
            raise

    def update(self, instance, validated_data, **kwargs):
        org = self.context["request"].user
        try:
            with transaction.atomic():
                instance.name = validated_data.get("name", instance.name)
                instance.description = validated_data.get(
                    "description", instance.description
                )

                if self.partial:
                    for _filter in validated_data["filters"]:
                        Filter.objects.update_or_create(
                            audience=instance,
                            property=_filter.get("property"),
                            defaults={
                                "operator": _filter.get("operator"),
                                "value": _filter.get("value"),
                            },
                        )
                else:
                    Filter.objects.filter(audience=instance).delete()
                    for _filter in validated_data["filters"]:
                        Filter.objects.create(audience=instance, **_filter)

                logging.info(
                    "Audience with id: %s updated for org: %s", instance.id, org.id
                )
                return instance
        except DatabaseError as error:
            logging.error(
                "Failed to update audience for org: %s with error: %s", org.id, error
            )
            raise
