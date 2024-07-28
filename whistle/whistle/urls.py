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

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from audience.views import AudienceViewSet
from connector.views import SendgridViewSet, TwilioViewSet, APNSViewSet, FCMViewSet
from external_user.views import ExternalUserViewSet, ExternalUserDeviceViewSet
from notification.views import NotificationViewSet, BroadcastViewSet
from organization.views import OrganizationViewSet, OrganizationCredentialsViewSet
from preference.views import ExternalUserPreferenceViewSet
from subscription.views import ExternalUserSubscriptionViewSet

# DO NOT REMOVE used for openapi spec generation
import whistle.extensions

v1_router = DefaultRouter()
v1_router.register(
    r"organizations/credentials",
    OrganizationCredentialsViewSet,
    basename="organizations.credentials",
)
v1_router.register(r"organizations", OrganizationViewSet, basename="organizations")
v1_router.register(r"users", ExternalUserViewSet, basename="external_users")
v1_router.register(
    r"devices", ExternalUserDeviceViewSet, basename="external_users_devices"
)
v1_router.register(
    r"preferences", ExternalUserPreferenceViewSet, basename="preferences"
)
v1_router.register(
    r"subscriptions", ExternalUserSubscriptionViewSet, basename="subscriptions"
)
v1_router.register(r"broadcasts", BroadcastViewSet, basename="broadcasts")
v1_router.register(r"notifications", NotificationViewSet, basename="notifications")
v1_router.register(r"connectors/twilio", TwilioViewSet, basename="connectors.twilio")
v1_router.register(
    r"connectors/sendgrid", SendgridViewSet, basename="connectors.sendgrid"
)
v1_router.register(r"connectors/apns", APNSViewSet, basename="connectors.apns")
v1_router.register(r"connectors/fcm", FCMViewSet, basename="connectors.fcm")
v1_router.register(r"audiences", AudienceViewSet, basename="audiences")

urlpatterns = [
    path("admin/", admin.site.urls),
    path(r"health/", include("health_check.urls")),
    path("api/v1/", include(v1_router.urls)),
]
