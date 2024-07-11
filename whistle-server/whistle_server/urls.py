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

from connector.views import SendgridViewSet, TwilioViewSet
from external_user.views import ExternalUserViewSet
from notification.views import NotificationViewSet, BatchNotificationViewSet
from organization.views import OrganizationViewSet
from preference.views import ExternalUserPreferenceViewSet
from subscription.views import ExternalUserSubscriptionViewSet

v1_router = DefaultRouter()
v1_router.register(r"organizations", OrganizationViewSet, basename="organizations")
v1_router.register(r"users", ExternalUserViewSet, basename="external_users")
v1_router.register(
    r"preferences", ExternalUserPreferenceViewSet, basename="preferences"
)
v1_router.register(
    r"subscriptions", ExternalUserSubscriptionViewSet, basename="subscriptions"
)
v1_router.register(
    r"notifications/batch",
    BatchNotificationViewSet,
    basename="notifications-batch",
)
v1_router.register(r"notifications", NotificationViewSet, basename="notifications")
v1_router.register(r"connectors/twilio", TwilioViewSet, basename="connectors.twilio")
v1_router.register(
    r"connectors/sendgrid", SendgridViewSet, basename="connectors.sendgrid"
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path(r"health/", include("health_check.urls")),
    path("api/v1/", include(v1_router.urls)),
]
