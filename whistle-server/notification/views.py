import logging
import uuid

from django.http import JsonResponse
from rest_framework import mixins, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import GenericViewSet

from external_user.models import ExternalUser
from notification.models import Notification, BatchNotification
from notification.serializers import (
    NotificationSerializer,
    BatchNotificationSerializer,
)
from whistle_server.auth import (
    ClientAuth,
    ServerAuth,
    IsValidExternalId,
)
from .tasks import send_batch_notification


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    authentication_classes = [ClientAuth]
    permission_classes = [AllowAny]

    def get_authenticators(self):
        if self.request.headers.get("X-External-Id") is None:
            return [ServerAuth()]
        return super(NotificationViewSet, self).get_authenticators()

    def get_permissions(self):
        if self.request.headers.get("X-External-Id") is not None:
            return [IsValidExternalId()]
        return [AllowAny()]

    def get_queryset(self):
        external_id = self.request.headers.get("X-External-Id")
        if external_id is not None:
            try:
                user = ExternalUser.objects.get(external_id=external_id)
            except ExternalUser.DoesNotExist:
                logging.error(
                    "Invalid external id: %s provided for org: %s",
                    external_id,
                    self.request.user.id,
                )
                raise ValidationError(
                    "Invalid External Id. Please provide a valid External Id in the request header.",
                    "invalid_external_id",
                )
            return self.queryset.filter(organization=self.request.user, recipient=user)
        else:
            return self.queryset.filter(organization=self.request.user)


class BatchNotificationViewSet(
    CreateAPIView,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = BatchNotification.objects.all()
    serializer_class = BatchNotificationSerializer
    authentication_classes = [ServerAuth]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch_id = uuid.uuid4()
        send_batch_notification.delay(batch_id, self.request.user.id, serializer.data)
        return JsonResponse(
            {"id": batch_id, **serializer.data},
            status=status.HTTP_200_OK,
        )
