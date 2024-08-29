from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path, re_path
from app import consumers

websocket_urlpattern = [
    path('api/v1/chat/<str:chat_id>/ws/', consumers.ChatConsumer.as_asgi()),
]