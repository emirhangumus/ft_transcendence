from django.urls import path
from app import consumers

websocket_urlpattern = [
    path('api/v1/chat/<str:chat_id>/ws/', consumers.ChatConsumer.as_asgi()),
    path('api/v1/game/<str:game_id>/ws/', consumers.GameConsumer.as_asgi()),
    path('api/v1/notification/ws/', consumers.NotificationConsumer.as_asgi()),
    path('api/v1/tournament/<str:tournament_id>/ws/', consumers.TournamentConsumer.as_asgi()),
]