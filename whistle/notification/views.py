import logging
import uuid
from datetime import datetime, timezone, timedelta

from celery.schedules import schedule
from django.db import transaction
from django.http import JsonResponse
from redbeat import RedBeatSchedulerEntry, RedBeatScheduler
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from external_user.models import ExternalUser
from notification.models import (
    Notification,
    Broadcast,
    BroadcastStatusChoices,
    DeliveryStatusChoices,
)
from notification.serializers import (
    NotificationSerializer,
    BroadcastSerializer,
    NotificationStatusSerializer,
    InboxSerializer,
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


class InboxViewSet(ReadOnlyModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = InboxSerializer
    authentication_classes = [ClientAuth]
    permission_classes = [IsValidExternalId]
    pagination_class = StandardLimitOffsetPagination

    def get_serializer_class(self):
        extra_actions = [action.__name__ for action in self.get_extra_actions()]
        if self.action in extra_actions:
            return NotificationStatusSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        external_id = self.request.headers.get("X-External-Id")
        org = self.request.user
        try:
            user = ExternalUser.objects.get(
                external_id=external_id,
                organization=self.request.user,
            )
        except ExternalUser.DoesNotExist:
            logging.error(
                "Invalid external id: %s provided for org: %s while querying preferences",
                external_id,
                self.request.user.id,
            )
            raise ValidationError(
                "Invalid External Id. Please provide a valid External Id in the request header.",
                "invalid_external_id",
            )
        return self.queryset.prefetch_related("deliveries").filter(
            recipient=user,
            organization=org,
            deliveries__channel=ChannelChoices.IN_APP,
            deliveries__status=DeliveryStatusChoices.DELIVERED,
        )

    @action(methods=["POST"], detail=True)
    def read(self, request, **kwargs):
        notification = self.get_object()
        notification.read_at = datetime.now(timezone.utc)
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True)
    def unread(self, request, **kwargs):
        notification = self.get_object()
        notification.read_at = None
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True)
    def seen(self, request, **kwargs):
        notification = self.get_object()
        notification.seen_at = datetime.now(timezone.utc)
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True)
    def archive(self, request, **kwargs):
        notification = self.get_object()
        notification.archived_at = datetime.now(timezone.utc)
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True)
    def unarchive(self, request, **kwargs):
        notification = self.get_object()
        notification.archived_at = None
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True)
    def clicked(self, request, **kwargs):
        notification = self.get_object()
        notification.clicked_at = datetime.now(timezone.utc)
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationViewSet(ReadOnlyModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    authentication_classes = [ServerAuth]
    pagination_class = StandardLimitOffsetPagination

    def get_serializer_class(self):
        extra_actions = [action.__name__ for action in self.get_extra_actions()]
        if self.action in extra_actions:
            return NotificationStatusSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        org = self.request.user
        return self.queryset.filter(organization=org)


class BroadcastViewSet(
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        persisted_data = serializer.validated_data.copy()
        persisted_data.pop("recipients")
        persisted_data.pop("channels")
        persisted_data.pop("merge_tags")

        idempotency_id = request.headers.get("IDEMPOTENCY-ID", uuid.uuid4())
        instance, created = Broadcast.objects.get_or_create(
            organization_id=self.request.user.id,
            idempotency_id=idempotency_id,
            defaults={
                **persisted_data,
                "status": BroadcastStatusChoices.QUEUED,
                "sent_at": datetime.now(timezone.utc),
            },
        )

        if not created:
            return JsonResponse(
                data={
                    "id": instance.id,
                    **serializer.validated_data,
                    "status": instance.status,
                }
            )

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
            status=status.HTTP_202_ACCEPTED,
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
            broadcast.status = BroadcastStatusChoices.FAILED
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
            broadcast.status = BroadcastStatusChoices.SCHEDULED
            broadcast.save()
            logging.info(
                "Broadcast scheduled at: %s with id: %s for org: %s",
                schedule_at,
                broadcast.id,
                self.request.user.id,
            )
            return
        except Exception as error:
            broadcast.status = BroadcastStatusChoices.FAILED
            broadcast.save()
            logging.error(
                "Failed to schedule broadcast: %s in org: %s with error: %s",
                broadcast.id,
                self.request.user.id,
                error,
            )
            raise

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        if instance.schedule_at and instance.status == "scheduled":
            serializer = self.get_serializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            key = f"redbeat:broadcast_{instance.id}"
            entry = RedBeatScheduler(app=app).Entry.from_key(key=key, app=app)
            entry.update(serializer.validated_data)

            if getattr(instance, "_prefetched_objects_cache", None):
                # If 'prefetch_related' has been applied to a queryset, we need to
                # forcibly invalidate the prefetch cache on the instance.
                instance._prefetched_objects_cache = {}

            return Response(serializer.validated_data)
        else:
            raise ValidationError(
                "The broadcast cannot be updated because it has already been processed or is not scheduled."
            )

    @transaction.atomic
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
                "The broadcast cannot be cancelled because it has already been processed or is not scheduled."
            )
