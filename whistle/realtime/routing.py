from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/", consumers.NotificationConsumer.as_asgi()),
]
