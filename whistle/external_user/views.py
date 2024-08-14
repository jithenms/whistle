import logging

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet, GenericViewSet

from external_user.models import (
    ExternalUser,
    ExternalUserDevice,
)
from external_user.serializers import (
    ExternalUserSerializer,
    ExternalUserDeviceSerializer,
)
from whistle.auth import (
    ServerAuth,
    ClientAuth,
    IsValidExternalId,
)
from whistle.pagination import StandardLimitOffsetPagination


class ExternalUserImportViewSet(GenericViewSet):
    queryset = ExternalUser.objects.all()
    serializer_class = ExternalUserSerializer
    authentication_classes = [ServerAuth]

    @extend_schema(
        request=ExternalUserSerializer(many=True),
        responses={201: ExternalUserSerializer(many=True)},
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        serializer.save()

    def get_success_headers(self, data):
        try:
            return {"Location": str(data[api_settings.URL_FIELD_NAME])}
        except (TypeError, KeyError):
            return {}


class ExternalUserViewSet(ModelViewSet):
    queryset = ExternalUser.objects.all()
    serializer_class = ExternalUserSerializer
    authentication_classes = [ServerAuth]
    pagination_class = StandardLimitOffsetPagination

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class DeviceViewSet(ModelViewSet):
    queryset = ExternalUserDevice.objects.all()
    serializer_class = ExternalUserDeviceSerializer
    authentication_classes = [ClientAuth]
    permission_classes = [IsValidExternalId]

    def get_queryset(self):
        external_id = self.request.headers.get("X-External-Id")
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
        return self.queryset.filter(user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"external_id": self.request.headers.get("X-External-Id")})
        return context
