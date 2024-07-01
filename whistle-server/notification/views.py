import os

from django.conf import settings
from django.http import JsonResponse
from rest_framework import mixins, status
from rest_framework.generics import CreateAPIView
from rest_framework.viewsets import GenericViewSet

from account.serializers import AccountSerializer
from authn.authentication import ClientAuthentication, ServerAuthentication, IsValidExternalId
from notification.tasks import send_notification
from notification.models import Notification
from notification.serializers import NotificationSerializer


class NotificationViewSet(CreateAPIView, mixins.ListModelMixin, mixins.UpdateModelMixin, mixins.RetrieveModelMixin,
                          GenericViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    authentication_classes = [ClientAuthentication]

    def get_authenticators(self):
        if self.request.method == 'POST':
            return [ServerAuthentication()]
        return super(NotificationViewSet, self).get_authenticators()

    def get_queryset(self):
        return self.queryset.filter(account=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_notification.delay(serializer.data, AccountSerializer(request.user).data)
        return JsonResponse({
            'status': 'queued',
        }, status=status.HTTP_202_ACCEPTED)
