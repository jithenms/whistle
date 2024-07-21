import logging
import uuid
from datetime import datetime, timedelta

from django.http import JsonResponse
from rest_framework import mixins, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import GenericViewSet

from audience.models import Audience
from external_user.models import ExternalUser
from notification.models import Notification, Broadcast
from notification.serializers import (
    NotificationSerializer,
    BroadcastSerializer,
)
from whistle_server.auth import (
    ClientAuth,
    ServerAuth,
    IsValidExternalId,
)
from whistle_server.pagination import StandardLimitOffsetPagination
from .tasks import schedule_broadcast, send_broadcast

from drf_spectacular.utils import extend_schema, OpenApiParameter


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
    pagination_class = StandardLimitOffsetPagination

    def get_queryset(self):
        org = self.request.user
        return self.queryset.filter(organization=org)

    def get_authenticators(self):
        external_id = (
            self.request.headers.get("X-External-Id") if self.request else None
        )
        if external_id is None:
            return [ServerAuth()]
        return super(NotificationViewSet, self).get_authenticators()

    def get_permissions(self):
        external_id = (
            self.request.headers.get("X-External-Id") if self.request else None
        )
        if external_id is not None:
            return [IsValidExternalId()]
        return [AllowAny()]

    def get_queryset(self):
        external_id = (
            self.request.headers.get("X-External-Id") if self.request else None
        )
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

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="X-External-Id",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID",
            ),
            OpenApiParameter(
                name="X-External-Id-Hmac",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID HMAC",
            ),
        ]
    )
    def list(self, request):
        return super().list(request)


class BroadcastViewSet(
    CreateAPIView,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Broadcast.objects.all()
    serializer_class = BroadcastSerializer
    authentication_classes = [ServerAuth]
    pagination_class = StandardLimitOffsetPagination

    def get_queryset(self):
        org = self.request.user
        return self.queryset.filter(organization=org)

    def create(self, request, *args, **kwargs):
        broadcast_id = uuid.uuid4()
        serializer = self.get_serializer(data={"id": broadcast_id, **request.data})
        serializer.is_valid(raise_exception=True)

        if "audience_id" in serializer.validated_data:
            try:
                Audience.objects.get(
                    organization=request.user,
                    pk=serializer.validated_data["audience_id"],
                )
            except Audience.DoesNotExist:
                logging.error(
                    "Invalid audience id: %s provided for org: %s",
                    serializer.validated_data["audience_id"],
                    request.user.id,
                )
                raise ValidationError(
                    "Audience not found. Please provide a valid Audience ID.",
                    "invalid_audience_id",
                )

        instance = serializer.save(status="queued")
        try:
            schedule_at = serializer.validated_data.get("schedule_at")
            if schedule_at and schedule_at - datetime.now(
                tz=schedule_at.tzinfo
            ) > timedelta(0):
                schedule_broadcast.delay(
                    str(broadcast_id),
                    str(self.request.user.id),
                    serializer.validated_data,
                )
            else:
                send_broadcast.delay(
                    str(broadcast_id),
                    str(self.request.user.id),
                    serializer.validated_data,
                )
                logging.info(
                    "Broadcast queued with id: %s for org: %s",
                    broadcast_id,
                    self.request.user.id,
                )
        except Exception as error:
            logging.debug(error)
            instance.status = "failed"
            instance.save()
            logging.info(
                "Broadcast failed to queue with id: %s for org: %s",
                broadcast_id,
                self.request.user.id,
            )
        response_data = serializer.validated_data
        if "channels" in response_data:
            response_data.pop("channels")
        if "filters" in response_data:
            response_data.pop("filters")
        return JsonResponse(
            {**response_data, "status": instance.status},
            status=status.HTTP_200_OK,
        )
