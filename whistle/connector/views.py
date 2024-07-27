from rest_framework.viewsets import ModelViewSet

from connector.models import Twilio, Sendgrid, APNS, FCM
from connector.serializers import (
    TwilioSerializer,
    SendgridSerializer,
    APNSSerializer,
    FCMSerializer,
)
from whistle.auth import ServerAuth


class TwilioViewSet(ModelViewSet):
    queryset = Twilio.objects.all()
    serializer_class = TwilioSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class SendgridViewSet(ModelViewSet):
    queryset = Sendgrid.objects.all()
    serializer_class = SendgridSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class APNSViewSet(ModelViewSet):
    queryset = APNS.objects.all()
    serializer_class = APNSSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class FCMViewSet(ModelViewSet):
    queryset = FCM.objects.all()
    serializer_class = FCMSerializer
    authentication_classes = [ServerAuth]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)
