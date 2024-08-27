from django.contrib import admin
from django.urls import path
from .views import HomeView, RegisterView, LoginView, FriendsView, ChatView, ChatCreateView, serve_dynamic_image
from . import consumers

urlpatterns = [
    path('static/<str:filename>/', serve_dynamic_image, name='serve_dynamic_image'),
    
    path('', HomeView.as_view(), name='home'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),

    path('friend/', FriendsView.as_view(), name='friends'),
    
    # path("chat/ws/", consumers.ChatConsumer, name='chat_ws'),
    path('chat/new/', ChatCreateView.as_view(), name='new_chat'),
    path('chat/<str:chat_id>/', ChatView.as_view(), name='chat_room'),
    path('chat/', ChatView.as_view(), name='chat'),

]
