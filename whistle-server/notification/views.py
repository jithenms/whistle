from django.http import JsonResponse
from rest_framework import mixins, status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import GenericViewSet

from external_user.models import ExternalUser
from notification.models import Notification
from notification.serializers import NotificationSerializer
from notification.tasks import send_notification
from whistle_server.middleware import (
    ClientAuthentication,
    ServerAuthentication,
    IsValidExternalId,
)


class NotificationViewSet(
    CreateAPIView,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    authentication_classes = [ClientAuthentication]
    permission_classes = [AllowAny]

    def get_authenticators(self):
        if (
            self.request.method == "POST"
            or self.request.headers.get("X-External-Id") is None
        ):
            return [ServerAuthentication()]
        return super(NotificationViewSet, self).get_authenticators()

    def get_queryset(self):
        if self.request.headers.get("X-External-Id") is not None:
            user = ExternalUser.objects.get(
                external_id=self.request.headers.get("X-External-Id")
            )
            return self.queryset.filter(organization=self.request.user, recipient=user)
        else:
            return self.queryset.filter(organization=self.request.user)

    def get_permissions(self):
        if (
            self.action != "create"
            and self.request.headers.get("X-External-Id") is not None
        ):
            return [IsValidExternalId()]
        return [AllowAny()]

    def create(self, request, *args, **kwargs):
        external_id = request.data["external_id"]
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_notification.delay(external_id, request.user.id, serializer.data)
        return JsonResponse(
            {
                "status": "queued",
            },
            status=status.HTTP_202_ACCEPTED,
        )
