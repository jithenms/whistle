from django.http import JsonResponse
from rest_framework import mixins, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.viewsets import GenericViewSet

from user.models import User
from user.serializers import UserSerializer


class UserViewSet(mixins.CreateModelMixin,
                  RetrieveAPIView,
                  GenericViewSet
                  ):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(request._user)
        response = JsonResponse(serializer.data, status=status.HTTP_200_OK, safe=False)
        return response
