from django.contrib import admin
from django.urls import path
from .views import HomeView, RegisterView, LoginView, FriendsView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),

    path('friend/', FriendsView.as_view(), name='friends'),
]
