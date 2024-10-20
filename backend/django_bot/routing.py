from django.urls import re_path
from .consumers import BotConsumer

websocket_urlpatterns = [
    re_path(r'ws/django_bot/$', BotConsumer.as_asgi()),
]

