"""
ASGI config for learnproject project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from myapp.routing import websocket_urlpatterns
from myapp.middleware import TokenAuthMiddlewareStack  # ✅ new import

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnproject.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": TokenAuthMiddlewareStack(  # ✅ use custom stack
        URLRouter(websocket_urlpatterns)
    ),
})


