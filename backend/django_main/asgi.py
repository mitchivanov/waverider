"""
ASGI config for trading_bot project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import django_bot.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_main.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # Add this line to handle HTTP requests
    "websocket": AuthMiddlewareStack(
        URLRouter(
            django_bot.routing.websocket_urlpatterns
        )
    ),
})
