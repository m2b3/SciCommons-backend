import os
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

# from app.consumers import ChatConsumer
import app.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Website.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(app.routing.websocket_urlpatterns))
        ),
    }
)

