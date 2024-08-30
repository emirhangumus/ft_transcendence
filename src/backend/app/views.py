from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from django.contrib.auth.models import User
from .serializers import UserSerializer, LoginSerializer, FriendRequestActionsSerializer, GameCreationSerilizer
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import render
from django.template.response import TemplateResponse
from .utils import genResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Friendships
from .queries.friend import getFriendState, getFriends
from .queries.chat import getChatRooms, getChatRoom, getChatMessages, createChatRoom
import os
from django.conf import settings
from django.http import HttpResponse, Http404, JsonResponse
from .logic import PongGame
import threading
import time

# Create your views here.
def serve_dynamic_image(request, filename):
    ROOT = settings.STATICFILES_DIRS[0]
    image_path = os.path.join(ROOT, 'images', filename)
    print(image_path)

    if os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            return HttpResponse(f.read(), content_type="image/jpeg")
    else:
        raise Http404("Image not found")

class HomeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        
        user = request.user
        friend_dict = getFriendState(user)
        
        return TemplateResponse(request, 'home.html', {} | friend_dict)

class RegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    
    def get(self, request):
        return TemplateResponse(request, 'register.html')
    
    def post(self, request):
        try: 
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                response = genResponse(True, "User registered successfully", None)
                return Response(response, status=status.HTTP_201_CREATED)
            response = genResponse(False, "User registration failed", serializer.errors)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
    
class LoginView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def get(self, request):
        return TemplateResponse(request, 'login.html')
    
    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            if serializer.is_valid():
                email = serializer.validated_data['email']
                user = User.objects.filter(email=email).first()
                refresh = RefreshToken.for_user(user)
                t_response = genResponse(True, "User logged in successfully", None)
                response = Response(t_response, status=status.HTTP_200_OK)
                response.set_cookie(key='refresh_token', value=refresh, httponly=False)
                response.set_cookie(key='access_token', value=refresh.access_token, httponly=False)
                return response
            response = genResponse(False, "User login failed", serializer.errors)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        
class FriendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        friend_dict = getFriendState(user)
        return render(request, 'friends.html', {} | friend_dict)
    
    def post(self, request):
        try:
            user = request.user
            target_friend = request.data['username']
            
            # if target_friend is not in the database, return error
            if not User.objects.filter(username=target_friend).exists():
                response = genResponse(False, "User not found", None)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            else:
                target_friend = User.objects.get(username=target_friend)
            
            # if target_friend is the same as the user, return error
            if user == target_friend:
                response = genResponse(False, "You cannot add yourself as friend", None)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            
            # if target_friend is already a friend, return error
            if user.friendships_sender_set.filter(receiver=target_friend).exists() or user.friendships_receiver_set.filter(sender=target_friend).exists():
                response = genResponse(False, "User is already a friend", None)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            
            # if target_friend has a pending request, return error
            if target_friend.friendships_sender_set.filter(receiver=user, status='pending').exists():
                response = genResponse(False, "Friend request already sent", None)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            
            # send friend request
            friendship = Friendships(sender=user, receiver=target_friend, status='pending')
            friendship.save()
            response = genResponse(True, "Friend request sent", None)
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        try:
            user = request.user
            print("suprise ", user)
            data = {
                'action': request.query_params['action'],
                'username': request.query_params['username']
            }
            serializer = FriendRequestActionsSerializer(data=data, context={'request': request})
            
            if serializer.is_valid():
                serializer.update(user, serializer.validated_data)
                response = genResponse(True, "Friend request updated", None)
                return Response(response, status=status.HTTP_200_OK)
            response = genResponse(False, "Friend request update failed", serializer.errors)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        
class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id=None):
        user = request.user
        
        chatRooms = getChatRooms(user.id)
        if (chat_id):
            chatRoom = getChatRoom(user.id, chat_id)
            if chatRoom:
                return TemplateResponse(request, 'chat.html', {'user': user, 'chatRooms': chatRooms, 'chatRoom': {
                    'id': chatRoom.room.id,
                    'chat_id': chatRoom.room.chat_id,
                    'name': chatRoom.room.name,
                    'can_leave': chatRoom.room.can_leave,
                    'messages': getChatMessages(chatRoom.room.id, 10)
                }})
        return TemplateResponse(request, 'chat.html', {'user': user, 'chatRooms': chatRooms})
    
class ChatCreateView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        friend_dict = getFriends(request.user)
        print(friend_dict)
        return TemplateResponse(request, 'chat_create.html', {'friends': friend_dict})

    def post(self, request):
        try:
            user = request.user
            data = request.data
            users = data['users']
            name = data['name']
            chatRoom = createChatRoom(name, user, users)
            if chatRoom:
                response = genResponse(True, "Chat room created successfully", None)
                return Response(response, status=status.HTTP_201_CREATED)
            response = genResponse(False, "Chat room creation failed", None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

class GameView(APIView):
    # game = PongGame(width=800, height=600)
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return TemplateResponse(request, 'game/waiting_room.html')

    # def doCrawl(self, task_id):
    #     while True:
    #         self.game.update()
    #         print("thread")
    #         time.sleep(1)

    # def pong_game(self, request):
    #     if request.method == "POST":
    #         direction = request.POST.get("direction")
    #         if direction:
    #             self.game.move_player(direction)
    #         return JsonResponse({
    #             "data": {
    #                 "ball_x": self.game.ball_x,
    #                 "ball_y": self.game.ball_y,
    #                 "player_y": self.game.player_y,
    #                 "ai_y": self.game.ai_y,
    #             }
    #         })
    #     else:
    #         # t = threading.Thread(target=doCrawl,args=[1],daemon=True)
    #         # t.start()
    #         self.game.update()
            
    #         return render(request, 'pong/pong_game.html', {
    #             "data": {
    #                 "ball_x": self.game.ball_x,
    #                 "ball_y": self.game.ball_y,
    #                 "player_y": self.game.player_y,
    #                 "ai_y": self.game.ai_y,
    #             }
    #         })

class GameCreateView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            serilizer = GameCreationSerilizer(data=request.data)
            if serilizer.is_valid():
                data = serilizer.validated_data
                game = PongGame(data)
            else:
                response = genResponse(False, "Invalid data", serilizer.errors)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)