from django.contrib import admin
from django.urls import path
from .views import HomeView, RegisterView, LoginView, TwoFactorAuthView, FriendsView, ChatView, ChatCreateView, serve_dynamic_image, GameView, GameCreateView, GamePlayView, TournamentView, TournamentCreateView, ProfileView, EditProfileView, UserProfileView, TournamentView
from . import consumers

urlpatterns = [
    path('static/<str:filename>/', serve_dynamic_image, name='serve_dynamic_image'),
    
    path('', HomeView.as_view(), name='home'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/2fa/', TwoFactorAuthView.as_view(), name='2fa'),

    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    path('profile/<str:username>/', UserProfileView.as_view(), name='user_profile'),

    path('friend/', FriendsView.as_view(), name='friends'),
    
    path('chat/', ChatView.as_view(), name='chat'),
    path('chat/new/', ChatCreateView.as_view(), name='new_chat'),
    path('chat/<str:chat_id>/', ChatView.as_view(), name='chat_room'),
    
    path('play/ai', GameView.as_view(), name='play_ai'),
    path('play/multi', GameView.as_view(), name='play_multi'),
    path('game/create/', GameCreateView.as_view(), name='create_game'),
    path('game/<str:game_id>/', GamePlayView.as_view(), name='game'),
    
    path('tournament/', TournamentView.as_view(), name='tournament'),
    path('tournament/new/', TournamentCreateView.as_view(), name='create_tournament'),
    path('tournament/<str:tournament_id>/', TournamentView.as_view(), name='tournament_room'),
]
