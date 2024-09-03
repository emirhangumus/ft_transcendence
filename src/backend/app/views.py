from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from django.contrib.auth.models import User
from .serializers import UserSerializer, LoginSerializer, FriendRequestActionsSerializer, GameCreationSerilizer, TournamentSerializer, AccountSerializer, GameRecordSerializer
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, get_object_or_404
from django.template.response import TemplateResponse
from .utils import genResponse, generateRandomID, isValidUsername
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Friendships, GameRecords, GameStats, GameTypes, GamePlayers, Tournaments, Accounts
from .queries.friend import getFriendState, getFriends
from .queries.chat import getChatRooms, getChatRoom, getChatMessages, createChatRoom
import os
from .jwt import PingPongObtainPairSerializer
from django.conf import settings
from django.http import HttpResponse, Http404
from .logic import PongGame
from .consumers import game_rooms, tournamentManager
import requests
from django.shortcuts import redirect

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

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        account = get_object_or_404(Accounts, id=user)
        serializer = AccountSerializer(account)
        context = {'account': serializer.data}
        return TemplateResponse(request, 'profile.html', context)
    

# class UserProfileView(APIView):
#     permission_classes = [IsAuthenticated]  # Allow viewing profiles without authentication

#     def get(self, request, username):
#         user = get_object_or_404(User, username=username)
#         account = get_object_or_404(Accounts, id=user)
#         serializer = AccountSerializer(account)
#         context = {
#             'account': serializer.data,
#             'user': user,
#         }
#         return TemplateResponse(request, 'user_profile.html', context)
    
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]  # Allow viewing profiles without authentication

    def get(self, request, username):
        # Fetch the user and account based on the username
        user = get_object_or_404(User, username=username)
        account = get_object_or_404(Accounts, id=user)
        
        # Serialize the account information
        account_serializer = AccountSerializer(account)
        
        # Fetch all game records where the user participated
        game_players = GamePlayers.objects.filter(player_id=user)
        game_records = GameRecords.objects.filter(id__in=game_players.values('game_record_id')).order_by('-created_at') 
        game_count = game_records.count()

        # Pass the serialized data to the template
        context = {
            'account': account_serializer.data,
            'user': user,
            'records': game_records,
            'count': game_count,
        }
        
        return TemplateResponse(request, 'user_profile.html', context)

class EditProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        user = request.user
        account = get_object_or_404(Accounts, id=user)
        serializer = AccountSerializer(instance=account)
        context = {
            'form': serializer,
            'username': user.username,
        }
        return TemplateResponse(request, 'edit_profile.html', context)

    def post(self, request):
        try:
            user = request.user
            user = User.objects.get(id=user.id)
            account = Accounts.objects.get(id=user.id)
            if request.data['username']:
                if User.objects.filter(username=request.data['username']).exists() and request.data['username'] != user.username:
                    raise Exception("Username already exists")
                if not isValidUsername(request.data['username']):
                    raise Exception("Invalid username")
                user.username = request.data['username']
            if request.data['email']:
                if User.objects.filter(email=request.data['email']).exists() and request.data['email'] != user.email:
                    raise Exception("Email already exists")
                user.email = request.data['email']
            if request.data['first_name']:
                user.first_name = request.data['first_name']
            if request.data['last_name']:
                user.last_name = request.data['last_name']
            user.save()
            if request.data['bio']:
                account.bio = request.data['bio']
            if request.data['profile_picture_url']:
                account.profile_picture_url = request.data['profile_picture_url']
            account.save()
            response = genResponse(True, "Profile updated successfully", None)
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class HomeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        
        user = request.user
        user = User.objects.get(id=user.id)
        friend_dict = getFriendState(user)
        return TemplateResponse(request, 'home.html', {} | friend_dict | { "user": user })

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
                    'game': None,
                    'player1': None,
                    'player2': None
                }
                game_rooms['game_' + game_id]['game'] = PongGame(data, game_id)
                return Response(genResponse(True, "Game created successfully", { "game_id": game_id }), status=status.HTTP_201_CREATED)
            else:
                response = genResponse(False, "Invalid data", serilizer.errors)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

class TournamentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, tournament_id=None):
        tournaments = Tournaments.objects.filter(status='pending')
        if (tournament_id):
            tournament = Tournaments.objects.filter(tournament_id=tournament_id).first()
            if tournament:
                return TemplateResponse(request, 'tournament/tournament.html', {'tournament': tournament, 'tournaments': tournaments })
        return TemplateResponse(request, 'tournament/tournament.html', {'tournaments': tournaments})
    
class TournamentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return TemplateResponse(request, 'tournament/tournament_create.html')
    
    def post(self, request):
        try:
            data = request.data
            user = request.user
            tournament_serializer = TournamentSerializer(data=data['tournament'])
            game_serializer = GameCreationSerilizer(data=data['game'])
            if not tournament_serializer.is_valid():
                response = genResponse(False, "Invalid tournament data", tournament_serializer.errors)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            if not game_serializer.is_valid():
                response = genResponse(False, "Invalid game data", game_serializer.errors)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            tournament_data = tournament_serializer.validated_data
            game_data = game_serializer.validated_data
            tournament_id = generateRandomID('tournaments')
            created_user = User.objects.get(id=user.id)
            tournament = Tournaments.objects.create(tournament_id=tournament_id, created_by=created_user, name=tournament_data['name'], player_amount=tournament_data['player_amount'], status='pending', game_settings=game_data)
            tournamentManager.add_tournament(tournament_id, game_data)
            response = genResponse(True, "Tournament created successfully", { "tournament_id": tournament_id })
            return Response(response, status=status.HTTP_201_CREATED)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
