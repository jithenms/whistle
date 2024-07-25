import logging

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from external_user.models import ExternalUser
from subscription.models import ExternalUserSubscription
from subscription.serializers import ExternalUserSubscriptionSerializer
from whistle_server.auth import ClientAuth, IsValidExternalId


class ExternalUserSubscriptionViewSet(ModelViewSet):
    queryset = ExternalUserSubscription.objects.all()
    serializer_class = ExternalUserSubscriptionSerializer
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
                "Invalid external id: %s provided for org: %s while querying subscriptions",
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

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="X-External-Id",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID",
                required=True,
            ),
            OpenApiParameter(
                name="X-External-Id-Hmac",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID HMAC",
                required=True,
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="X-External-Id",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID",
                required=True,
            ),
            OpenApiParameter(
                name="X-External-Id-Hmac",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID HMAC",
                required=True,
            ),
        ]
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="X-External-Id",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID",
                required=True,
            ),
            OpenApiParameter(
                name="X-External-Id-Hmac",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID HMAC",
                required=True,
            ),
        ]
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="X-External-Id",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID",
                required=True,
            ),
            OpenApiParameter(
                name="X-External-Id-Hmac",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID HMAC",
                required=True,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="X-External-Id",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID",
                required=True,
            ),
            OpenApiParameter(
                name="X-External-Id-Hmac",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID HMAC",
                required=True,
            ),
        ]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="X-External-Id",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID",
                required=True,
            ),
            OpenApiParameter(
                name="X-External-Id-Hmac",
                type=str,
                location=OpenApiParameter.HEADER,
                description="External ID HMAC",
                required=True,
            ),
        ]
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
