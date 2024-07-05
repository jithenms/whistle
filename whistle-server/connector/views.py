from rest_framework.viewsets import ModelViewSet

from connector.models import Twilio, Sendgrid
from connector.serializers import TwilioSerializer, SendgridSerializer
from whistle_server.auth import ServerAuth


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
