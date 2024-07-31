import logging
from datetime import datetime, timezone, timedelta

from celery.schedules import schedule
from django.db import transaction
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter
from redbeat import RedBeatSchedulerEntry, RedBeatScheduler
from rest_framework import mixins, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from external_user.models import ExternalUser
from notification.models import Notification, Broadcast
from notification.serializers import (
    NotificationSerializer,
    BroadcastSerializer,
)
from preference.models import ChannelChoices
from whistle.auth import (
    ClientAuth,
    ServerAuth,
    IsValidExternalId,
)
from whistle.celery import app
from whistle.pagination import StandardLimitOffsetPagination
from .tasks import send_broadcast


class NotificationViewSet(
    mixins.ListModelMixin,
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
            return self.queryset.filter(
                organization=self.request.user,
                channel=ChannelChoices.IN_APP,
                recipient=user,
            )
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
    mixins.DestroyModelMixin,
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save(status="queued", sent_at=datetime.now(timezone.utc))

        schedule_at = serializer.validated_data.get("schedule_at")
        if schedule_at:
            self.schedule_broadcast(instance, serializer)
        else:
            self.queue_broadcast(instance, serializer)
        return JsonResponse(
            data={
                "id": instance.id,
                **serializer.validated_data,
                "status": instance.status,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic()
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.schedule_at and instance.status == "scheduled":
            key = f"redbeat:broadcast_{instance.id}"
            entry = RedBeatScheduler(app=app).Entry.from_key(key=key, app=app)
            entry.delete()
            super().perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            raise ValidationError(
                "The broadcast cannot be deleted because it has already been processed or is not scheduled."
            )

    def queue_broadcast(self, broadcast, serializer):
        try:
            redacted_data = serializer.validated_data.copy()
            redacted_data.update({"recipients": "***"})
            redacted_data.update({"merge_tags": "***"})
            send_broadcast.s(
                str(broadcast.id),
                str(self.request.user.id),
                data=serializer.validated_data,
            ).set(kwargsrepr=repr({"data": redacted_data})).apply_async()
            logging.info(
                "Broadcast queued with id: %s for org: %s",
                broadcast.id,
                self.request.user.id,
            )
            return
        except Exception as error:
            logging.error(
                "Failed to queue broadcast: %s in org: %s with error: %s",
                broadcast.id,
                self.request.user.id,
                error,
            )
            broadcast.status = "failed"
            broadcast.save()
            logging.info(
                "Broadcast failed to queue with id: %s for org: %s",
                broadcast.id,
                self.request.user.id,
            )
            raise

    def schedule_broadcast(self, broadcast, serializer):
        try:
            schedule_at = serializer.validated_data.get("schedule_at")
            entry = RedBeatSchedulerEntry(app=app)
            entry.name = f"broadcast_{broadcast.id}"
            entry.task = "notification.tasks.send_broadcast"
            entry.args = [
                str(broadcast.id),
                str(self.request.user.id),
                serializer.validated_data,
            ]
            entry.schedule = schedule(
                max(
                    schedule_at - datetime.now(tz=schedule_at.tzinfo),
                    timedelta(0),
                )
            )
            entry.save()
            broadcast.schedule_at = schedule_at
            broadcast.status = "scheduled"
            broadcast.save()
            logging.info(
                "Broadcast scheduled at: %s with id: %s for org: %s",
                schedule_at,
                broadcast.id,
                self.request.user.id,
            )
            return
        except Exception as error:
            broadcast.status = "failed"
            broadcast.save()
            logging.error(
                "Failed to schedule broadcast: %s in org: %s with error: %s",
                broadcast.id,
                self.request.user.id,
                error,
            )
            raise
