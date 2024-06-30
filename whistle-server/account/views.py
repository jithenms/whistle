from django.http import JsonResponse
from rest_framework import status, mixins, viewsets
from rest_framework.generics import RetrieveAPIView, UpdateAPIView, DestroyAPIView
from rest_framework.mixins import CreateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from account.models import Account
from account.serializers import AccountSerializer
from authn.authentication import ServerAuthentication


class AccountModelViewSet(viewsets.GenericViewSet):
    def get_object(self):
        return self.request.user


class AccountViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     AccountModelViewSet
                     ):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    authentication_classes = [ServerAuthentication]

    def get_authenticators(self):
        if self.request.method == 'POST':
            return []
        return super(AccountViewSet, self).get_authenticators()
