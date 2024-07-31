from rest_framework.viewsets import ModelViewSet

from provider.models import Provider, ProviderChoices
from provider.serializers import (
    TwilioSerializer,
    SendgridSerializer,
    APNSSerializer,
    FCMSerializer,
)
from whistle.auth import ServerAuth


class SendgridViewSet(ModelViewSet):
    queryset = Provider.objects.all()
    serializer_class = SendgridSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(
            organization=self.request.user, provider=ProviderChoices.SENDGRID
        )


class TwilioViewSet(ModelViewSet):
    queryset = Provider.objects.all()
    serializer_class = TwilioSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(
            organization=self.request.user, provider=ProviderChoices.TWILIO
        )


class APNSViewSet(ModelViewSet):
    queryset = Provider.objects.all()
    serializer_class = APNSSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(
            organization=self.request.user, provider=ProviderChoices.APNS
        )


class FCMViewSet(ModelViewSet):
    queryset = Provider.objects.all()
    serializer_class = FCMSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(
            organization=self.request.user, provider=ProviderChoices.FCM
        )
