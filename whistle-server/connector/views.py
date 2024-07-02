from rest_framework.viewsets import ModelViewSet

from connector.models import Twilio, Sendgrid
from connector.serializers import TwilioSerializer, SendgridSerializer
from whistle_server.middleware import ServerAuthentication


class TwilioViewSet(ModelViewSet):
    queryset = Twilio.objects.all()
    serializer_class = TwilioSerializer
    authentication_classes = [ServerAuthentication]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class SendgridViewSet(ModelViewSet):
    queryset = Sendgrid.objects.all()
    serializer_class = SendgridSerializer
    authentication_classes = [ServerAuthentication]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)
