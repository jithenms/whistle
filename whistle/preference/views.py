import logging

from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from external_user.models import ExternalUser
from preference.models import ExternalUserPreference
from preference.serializers import ExternalUserPreferenceSerializer
from whistle.auth import ClientAuth, IsValidExternalId


class PreferenceViewSet(ModelViewSet):
    queryset = ExternalUserPreference.objects.all()
    serializer_class = ExternalUserPreferenceSerializer
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
