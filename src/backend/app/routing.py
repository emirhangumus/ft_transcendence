from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path, re_path
from app import consumers

websocket_urlpattern = [
    # path('api/v1/ws/chat/<str:chat_id>/', consumers.ChatConsumer.as_asgi()),
    path('api/v1/ws/test/', consumers.ChatConsumer.as_asgi()),
]