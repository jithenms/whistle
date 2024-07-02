from rest_framework.viewsets import ModelViewSet

from authentication.middleware import ServerAuthentication, ClientAuthentication, IsValidExternalId
from user.models import User, UserPreference, UserSubscription
from user.serializers import UserSerializer, UserPreferenceSerializer, UserSubscriptionSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = [ServerAuthentication]

    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user)


class UserPreferenceViewSet(ModelViewSet):
    queryset = UserPreference.objects.all()
    serializer_class = UserPreferenceSerializer
    authentication_classes = [ClientAuthentication]
    permission_classes = [IsValidExternalId]

    def get_queryset(self):
        user = User.objects.get(external_id=self.request.headers.get('X-External-Id'), organization=self.request.user)
        return self.queryset.filter(user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"external_id": self.request.headers.get('X-External-Id')})
        return context


class UserSubscriptionViewSet(ModelViewSet):
    queryset = UserSubscription.objects.all()
    serializer_class = UserSubscriptionSerializer
    authentication_classes = [ClientAuthentication]
    permission_classes = [IsValidExternalId]

    def get_queryset(self):
        user = User.objects.get(external_id=self.request.headers.get('X-External-Id'), organization=self.request.user)
        return self.queryset.filter(user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"external_id": self.request.headers.get('X-External-Id')})
        return context
