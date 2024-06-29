from django.http import JsonResponse
from rest_framework import mixins, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.viewsets import GenericViewSet

from account.models import Account
from account.serializers import AccountSerializer


class AccountViewSet(mixins.CreateModelMixin,
                     RetrieveAPIView,
                     GenericViewSet
                     ):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.account)
        response = JsonResponse(serializer.data, status=status.HTTP_200_OK, safe=False)
        return response
