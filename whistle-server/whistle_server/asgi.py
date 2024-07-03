import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from realtime import routing
from realtime.middleware import ClientAuthMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whistle_server.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": ClientAuthMiddleware(URLRouter(routing.websocket_urlpatterns)),
    }
)
