"""
URL configuration for whistle_server project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from account.views import AccountViewSet
from authn.views import CredentialViewSet
from connector.views import SendgridViewSet, TwilioViewSet
from user.views import UserViewSet

router = DefaultRouter()
router.register(r'accounts', AccountViewSet, basename='account')
router.register(r'credentials', CredentialViewSet, basename='credential')
router.register(r'users', UserViewSet, basename='user')
router.register(r'connectors/twilio', TwilioViewSet, basename='twilio')
router.register(r'connectors/sendgrid', SendgridViewSet, basename='sendgrid')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
]
