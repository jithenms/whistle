from rest_framework.viewsets import ModelViewSet

from authn.authentication import ServerAuthentication
from user.models import User
from user.serializers import UserSerializer


class UserViewSet(ModelViewSet):
    lookup_field = "external_id"
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = [ServerAuthentication]

    def get_queryset(self):
        return self.queryset.filter(account=self.request.user)