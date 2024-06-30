from django.http import JsonResponse
from rest_framework import status, mixins
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.viewsets import GenericViewSet

from authn.authentication import ServerAuthentication
from user.models import User
from user.serializers import UserSerializer


class UserViewSet(CreateAPIView,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  mixins.ListModelMixin,
                  GenericViewSet
                  ):
    lookup_field = "external_id"
    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = [ServerAuthentication]

    def get_queryset(self):
        return self.queryset.filter(account=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse({'error': 'failed_to_create_user', 'error_description': "Invalid input"},
                                status=status.HTTP_400_BAD_REQUEST)
        serializer.save(account=request.user)
        response = JsonResponse(serializer.data, status=status.HTTP_201_CREATED,
                                safe=False)
        return response
