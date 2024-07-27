import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whistle.settings")

django_asgi_app = get_asgi_application()

from realtime import routing
from realtime.middleware import ClientAuthMiddleware

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": ClientAuthMiddleware(URLRouter(routing.websocket_urlpatterns)),
    }
)
