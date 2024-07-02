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
from external_user.views import (
    ExternalUserViewSet,
    ExternalUserPreferenceViewSet,
    ExternalUserSubscriptionViewSet,
)
from notification.views import NotificationViewSet
from organization.views import OrganizationViewSet
from webhook.views import ClerkWebhookViewSet

router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"users", ExternalUserViewSet, basename="external_user")
router.register(r"preferences", ExternalUserPreferenceViewSet, basename="preference")
router.register(
    r"subscriptions", ExternalUserSubscriptionViewSet, basename="subscription"
)
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"connectors/twilio", TwilioViewSet, basename="connector.twilio")
router.register(r"connectors/sendgrid", SendgridViewSet, basename="connector.sendgrid")
router.register(r"webhooks/clerk", ClerkWebhookViewSet, basename="webhook.clerk")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(router.urls)),
]
