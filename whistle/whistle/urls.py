"""
URL configuration for whistle project.

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

from django.urls import path, include
from rest_framework.routers import SimpleRouter

from audience.views import AudienceViewSet
from provider.views import TwilioViewSet, SendgridViewSet, APNSViewSet, FCMViewSet
from external_user.views import (
    ExternalUserViewSet,
    DeviceViewSet,
    ExternalUserImportViewSet,
)
from notification.views import (
    NotificationViewSet,
    BroadcastViewSet,
    InboxViewSet,
)
from organization.views import OrganizationViewSet, OrganizationCredentialsViewSet
from preference.views import PreferenceViewSet
from subscription.views import SubscriptionViewSet

# DO NOT REMOVE used for openapi spec generation
import whistle.extensions

v1_router = SimpleRouter(trailing_slash=False)
v1_router.register(
    r"organizations/credentials",
    OrganizationCredentialsViewSet,
    basename="organizations.credentials",
)
v1_router.register(r"organizations", OrganizationViewSet, basename="organizations")
v1_router.register(
    r"users/import", ExternalUserImportViewSet, basename="external_users.import"
)
v1_router.register(r"users", ExternalUserViewSet, basename="external_users")
v1_router.register(r"devices", DeviceViewSet, basename="devices")
v1_router.register(r"preferences", PreferenceViewSet, basename="preferences")
v1_router.register(r"subscriptions", SubscriptionViewSet, basename="subscriptions")
v1_router.register(r"broadcasts", BroadcastViewSet, basename="broadcasts")
v1_router.register(r"inbox", InboxViewSet, basename="inbox")
v1_router.register(r"notifications", NotificationViewSet, basename="notifications")
v1_router.register(
    r"providers/sendgrid", SendgridViewSet, basename="providers.sendgrid"
)
v1_router.register(r"providers/twilio", TwilioViewSet, basename="providers.twilio")
v1_router.register(r"providers/apns", APNSViewSet, basename="providers.apns")
v1_router.register(r"providers/fcm", FCMViewSet, basename="providers.fcm")
v1_router.register(r"audiences", AudienceViewSet, basename="audiences")

urlpatterns = [
    path(r"health", include("health_check.urls")),
    path(r"api/v1/", include(v1_router.urls)),
]
