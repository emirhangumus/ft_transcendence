from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from django.contrib.auth.models import User
from .serializers import UserSerializer, LoginSerializer, FriendRequestActionsSerializer, GameCreationSerilizer
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import render
from django.template.response import TemplateResponse
from .utils import genResponse, generateRandomID
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Friendships, GameRecords, GameStats, GameTypes, GamePlayers
from .queries.friend import getFriendState, getFriends
from .queries.chat import getChatRooms, getChatRoom, getChatMessages, createChatRoom
import os
from .jwt import PingPongObtainPairSerializer
from django.conf import settings
from django.http import HttpResponse, Http404, JsonResponse
from .logic import PongGame
import threading
import time
from .consumers import game_rooms, notificationManager

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
                refresh = PingPongObtainPairSerializer.get_token(user)
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
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return TemplateResponse(request, 'game/waiting_room.html')
    
class GamePlayView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, game_id=None):
        return TemplateResponse(request, 'game/play.html', {'game': { "id": game_id }})

class GameCreateView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            print(request.data)
            serilizer = GameCreationSerilizer(data=request.data)
            if serilizer.is_valid():
                user = request.user
                data = serilizer.validated_data
                game_id = generateRandomID('gamerecords')
                game_record = GameRecords.objects.create(game_id=game_id, player1_score=0, player2_score=0, winner_id=None, total_match_time=0)
                game_player = GamePlayers.objects.create(game_record=game_record, player_id=user)
                game_type = GameTypes.objects.create(game_record=game_record, payload=data)
                game_stat = GameStats.objects.create(game_record=game_record, stats={
                    "heatmap": []
                })

                game_rooms['game_' + game_id] = {
                    'game': PongGame(data),
                    'player1': None,
                    'player2': None
                }
                return Response(genResponse(True, "Game created successfully", { "game_id": game_id }), status=status.HTTP_201_CREATED)
                # game = PongGame(data)
                # t = threading.Thread(target=self.gameTread, daemon=True, args=[game])
                # t.start()
                # if (self.game.is_game_over):
                #     t.join()
                # return JsonResponse({
                #     "data": {
                #         "ball_x": self.game.ball_x,
                #         "ball_y": self.game.ball_y,
                #         "player_y": self.game.player_y,
                #         "ai_y": self.game.ai_y,
                #         "is_game_over": self.game.is_game_over,
                #         "player_score": self.game.player_score,
                #         "opp_score": self.game.opp_score,
                #         "ball_color": data["ball_color"],
                #         "background_color": data["background_color"],
                #     }
                # })
            else:
                response = genResponse(False, "Invalid data", serilizer.errors)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)