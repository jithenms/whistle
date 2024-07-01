from django.db import transaction
from rest_framework import serializers

from user.models import User, UserPreference, UserPreferenceChannel, UserSubscriptionCategory, UserSubscription


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'external_id', 'first_name', 'last_name', 'email', 'phone']

    def create(self, validated_data):
        validated_data['organization'] = self.context['request'].user
        return super().create(validated_data)


class UserPreferenceChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferenceChannel
        fields = ['id', 'slug', 'enabled']


class UserPreferenceSerializer(serializers.ModelSerializer):
    channels = UserPreferenceChannelSerializer(many=True)

    class Meta:
        model = UserPreference
        fields = ['id', 'slug', 'channels']

    @transaction.atomic
    def create(self, validated_data):
        channels_data = validated_data.pop('channels', [])
        external_user = User.objects.get(external_id=self.context.get('external_id'))
        user_preference = UserPreference.objects.create(user=external_user, slug=validated_data['slug'])

        default_channels = [
            {"slug": "web", "enabled": True},
            {"slug": "email", "enabled": True},
            {"slug": "sms", "enabled": True}
        ]

        for channel in channels_data:
            for default_channel in default_channels:
                if channel['slug'] == default_channel['slug']:
                    default_channel.update(channel)

        for channel in default_channels:
            UserPreferenceChannel.objects.create(user_preference=user_preference, **channel)
        return user_preference

    @transaction.atomic
    def update(self, instance, validated_data):
        channels_data = validated_data.pop('channels', [])
        instance.slug = validated_data.get('slug', instance.slug)
        instance.save()

        UserPreferenceChannel.objects.filter(user_preference=instance).delete()
        for channel_data in channels_data:
            UserPreferenceChannel.objects.create(user_preference=instance, **channel_data)
        return instance

    @transaction.atomic
    def partial_update(self, instance, validated_data):
        channels_data = validated_data.pop('channels', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if channels_data is not None:
            UserPreferenceChannel.objects.filter(user_preference=instance).delete()
            for channel_data in channels_data:
                UserPreferenceChannel.objects.create(user_preference=instance, **channel_data)

        return instance


class UserSubscriptionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSubscriptionCategory
        fields = ['id', 'slug', 'description']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    categories = UserSubscriptionCategorySerializer(many=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'topic', 'categories']

    @transaction.atomic
    def create(self, validated_data):
        category_data = validated_data.pop('categories', [])
        external_user = User.objects.get(external_id=self.context.get('external_id'))
        user_subscription = UserSubscription.objects.create(user=external_user, topic=validated_data['topic'])

        for cat in category_data:
            UserSubscriptionCategory.objects.create(user_subscription=user_subscription, **cat)
        return user_subscription

    @transaction.atomic
    def update(self, instance, validated_data):
        category_data = validated_data.pop('categories', [])
        instance.slug = validated_data.get('slug', instance.slug)
        instance.save()

        UserSubscriptionCategory.objects.filter(user_preference=instance).delete()
        for cat in category_data:
            UserSubscriptionCategory.objects.create(user_preference=instance, **cat)
        return instance

    @transaction.atomic
    def partial_update(self, instance, validated_data):
        category_data = validated_data.pop('categories', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if category_data is not None:
            UserSubscriptionCategory.objects.filter(user_preference=instance).delete()
            for cat in category_data:
                UserSubscriptionCategory.objects.create(user_preference=instance, **cat)

        return instance
