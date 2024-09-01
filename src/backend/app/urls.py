from django.contrib import admin
from django.urls import path
from .views import HomeView, RegisterView, LoginView, FriendsView, ChatView, ChatCreateView, serve_dynamic_image, GameView, GameCreateView, GamePlayView, TournamentView, TournamentCreateView
from . import consumers

urlpatterns = [
    path('static/<str:filename>/', serve_dynamic_image, name='serve_dynamic_image'),
    
    path('', HomeView.as_view(), name='home'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),

    path('friend/', FriendsView.as_view(), name='friends'),
    
    path('chat/', ChatView.as_view(), name='chat'),
    path('chat/new/', ChatCreateView.as_view(), name='new_chat'),
    path('chat/<str:chat_id>/', ChatView.as_view(), name='chat_room'),

    path('play/', GameView.as_view(), name='play'),
    path('game/create/', GameCreateView.as_view(), name='create_game'),
    path('game/<str:game_id>/', GamePlayView.as_view(), name='game'),
    
    path('tournament/', TournamentView.as_view(), name='tournament'),
    path('tournament/new/', TournamentCreateView.as_view(), name='create_tournament'),
    path('tournament/<str:tournament_id>/', TournamentView.as_view(), name='tournament_room'),
]
