from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from django.contrib.auth.models import User
from .serializers import UserSerializer, LoginSerializer, FriendRequestActionsSerializer, GameCreationSerilizer, TournamentSerializer, AccountSerializer, GameRecordSerializer
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, get_object_or_404
from django.template.response import TemplateResponse
from .utils import genResponse, generateRandomID, isValidUsername, generate2FAQRCode, generate_svg_pie_chart, validate2FA, generate_svg_heatmap_with_dynamic_size
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Friendships, GameRecords, GameStats, GameTypes, GamePlayers, Tournaments, Accounts, ChatMessages
from .queries.friend import getFriendState, getFriends
from .queries.chat import getChatRooms, getChatRoom, getChatMessages, createChatRoom, getFriendChatRooms, leaveChatRoom
import os
from .jwt import PingPongObtainPairSerializer
from django.conf import settings
from django.http import HttpResponse, Http404
from .logic import PongGame
from .consumers import game_rooms, tournamentManager, notificationManager
from django.db.models import Count
from django.shortcuts import redirect
from rest_framework.parsers import MultiPartParser, FormParser

# Create your views here.
def serve_dynamic_image(request, filename):
    ROOT = settings.STATICFILES_DIRS[0]
    image_path = os.path.join(ROOT, 'images', filename)

    if os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            return HttpResponse(f.read(), content_type="image/*")
    else:
        raise Http404("Image not found")

def serve_dynamic_media(request, filename):
    ROOT = settings.MEDIA_ROOT
    image_path = os.path.join(ROOT, 'profile_pictures', filename)

    print(image_path)

    if os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            return HttpResponse(f.read(), content_type="image/*")
    else:
        raise Http404("Image not found")

class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]  # Optionally, require authentication

    def get(self, request):
        # Aggregate the number of wins for each user
        leaderboard = (
            User.objects.filter(gamerecords__winner_id__isnull=False)  # Ensure the user has won games
            .annotate(win_count=Count('gamerecords__winner_id'))       # Count the wins
            .order_by('-win_count')[:5]                                # Get the top 5 users
        )

        # Fetch associated account info and pass it to the template
        leaderboard_data = []
        for user in leaderboard:
            account = Accounts.objects.get(id=user)
            leaderboard_data.append({
                'user': user,
                'wins': user.win_count,
                'bio': account.bio,
                'profile_picture_url': account.profile_picture_url,
            })

        # Determine how many users are being sent
        num_users = len(leaderboard_data)

        context = {
            'leaderboard': leaderboard_data,
            'num_users': num_users,  # Include the number of users in the context
        }

        return render(request, 'leaderboard.html', context)
    
class GameHeatMapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, game_id):
        # Fetch the game record
        game_record = get_object_or_404(GameRecords, game_id=game_id)

        # Fetch ball location data from the game stats
        game_stats = get_object_or_404(GameStats, game_record=game_record)
        ball_locations = game_stats.stats.get('heatmap', [])

        # Fetch map dimensions from the GameTypes payload
        game_type = get_object_or_404(GameTypes, game_record=game_record)
        map_width = game_type.payload.get('map_width', 800)  # Default to 800 if not found
        map_height = game_type.payload.get('map_height', 600)  # Default to 600 if not found

        # Generate the heatmap SVG with the correct dimensions
        heatmap_svg = generate_svg_heatmap_with_dynamic_size(ball_locations, map_width, map_height)

        # Pass the heatmap SVG and other game info to the template
        context = {
            'game_record': game_record,
            'heatmap_svg': heatmap_svg,
        }

        return TemplateResponse(request, 'game_heatmap.html', context)



class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        account = get_object_or_404(Accounts, id=user)
        serializer = AccountSerializer(account)
        context = {'account': serializer.data }
        return TemplateResponse(request, 'profile.html', context)

    
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

        # Count wins, losses, and ties
        wins = game_records.filter(winner_id=user.id).count()
        losses = game_records.exclude(winner_id=user.id).exclude(winner_id__isnull=True).count()
        ties = game_records.filter(winner_id__isnull=True).count()

        # Generate SVG pie chart for the statistics
        chart_svg = generate_svg_pie_chart(wins, losses, ties)

        # Pass the serialized data, game records, and chart data to the template
        context = {
            'account': account_serializer.data,
            'user': user,
            'records': game_records,
            'count': game_count,
            'chart_svg': chart_svg,
            'wins': wins,
            'losses': losses,
            'ties': ties,
        }
        
        return TemplateResponse(request, 'user_profile.html', context)


class EditProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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
            account = get_object_or_404(Accounts, id=user)
            username = request.data.get('username', user.username)
            first_name = request.data.get('first_name', user.first_name)
            last_name = request.data.get('last_name', user.last_name)
            email = request.data.get('email', user.email)
            bio = request.data.get('bio', account.bio)
            if username:
                if User.objects.filter(username=username).exists() and username != user.username:
                    raise Exception("Username already exists")
                if not isValidUsername(username):
                    raise Exception("Invalid username")
                user.username = username
            if email:
                if User.objects.filter(email=email).exists() and email != user.email:
                    raise Exception("Email already exists")
                user.email = email
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            if bio:
                account.bio = bio
            # Handle profile picture file if uploaded
            if 'profile_picture_url' in request.FILES:
                profile_picture_url = request.FILES['profile_picture_url']
                account.profile_picture_url = profile_picture_url  # Save the uploaded file to the model
            account.save()
            user.save()
            
            return Response({'detail': 'Profile updated successfully'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # def post(self, request):
    #     try:
    #         user = request.user
    #         user = User.objects.get(id=user.id)
    #         account = Accounts.objects.get(id=user.id)
    #         if request.data['username']:
    #             if User.objects.filter(username=request.data['username']).exists() and request.data['username'] != user.username:
    #                 raise Exception("Username already exists")
    #             if not isValidUsername(request.data['username']):
    #                 raise Exception("Invalid username")
    #             user.username = request.data['username']
    #         if request.data['email']:
    #             if User.objects.filter(email=request.data['email']).exists() and request.data['email'] != user.email:
    #                 raise Exception("Email already exists")
    #             user.email = request.data['email']
    #         if request.data['first_name']:
    #             user.first_name = request.data['first_name']
    #         if request.data['last_name']:
    #             user.last_name = request.data['last_name']
    #         user.save()
    #         if request.data['bio']:
    #             account.bio = request.data['bio']
    #         # if request.data['profile_picture_url']:
    #         #     account.profile_picture_url = request.data['profile_picture_url']
    #         if 'profile_picture_url' in request.FILES:
    #             profile_picture_url = request.FILES['profile_picture_url']
    #             account.profile_picture_url = profile_picture_url  # Save the uploaded file to the model
    #         account.save()
    #         response = genResponse(True, "Profile updated successfully", None)
    #         return Response(response, status=status.HTTP_200_OK)
    #     except Exception as e:
    #         response = genResponse(False, str(e), None)
    #         return Response(response, status=status.HTTP_400_BAD_REQUEST)


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
                
                # check the user's 2FA status
                if Accounts.objects.get(id=user.id).two_factor_auth:
                    code = request.data.get('code')
                    if not code:
                        response = genResponse(False, "two_factor_auth", None)
                        return Response(response, status=status.HTTP_200_OK)
                    if not validate2FA(code):
                        response = genResponse(False, "Two factor authentication failed", None)
                        return Response(response, status=status.HTTP_400_BAD_REQUEST)
                
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

class TwoFactorAuthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return TemplateResponse(request, '2fa.html')

    def post(self, request):
        try:
            user = request.user
            state = Accounts.objects.get(id=user.id).two_factor_auth
            if state:
                Accounts.objects.filter(id=user.id).update(two_factor_auth=False)
                response = genResponse(True, "Two factor authentication disabled", None)
                return Response(response, status=status.HTTP_200_OK)
            else:
                Accounts.objects.filter(id=user.id).update(two_factor_auth=True)
                qrcode = generate2FAQRCode(user.email)
                response = genResponse(True, "Two factor authentication enabled", { 'qrcode': qrcode })
                return Response(response, status=status.HTTP_200_OK)
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
    
class ChatLeave(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, chat_id):
        user = request.user
        chatRoom = getChatRoom(user.id, chat_id)
        if chatRoom:
            leaveChatRoom(chatRoom.room.id, user.id)
            chatRooms = getChatRooms(user.id)
            response = genResponse(True, "Chat room left successfully", { 'chatRooms': [{
                'chat_id': chatRoom.room.chat_id,
                'name': chatRoom.room.name,
                'can_leave': chatRoom.room.can_leave,
                } for chatRoom in chatRooms]
            })
            return Response(response, status=status.HTTP_200_OK)
        chatRooms = getChatRooms(user.id)
        response = genResponse(False, "Chat room not found", { 'chatRooms': [{
            'chat_id': chatRoom.room.chat_id,
            'name': chatRoom.room.name,
            'can_leave': chatRoom.room.can_leave,
            } for chatRoom in chatRooms]
        })
        return Response(response, status=status.HTTP_400_BAD_REQUEST)

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
        # get the requested path
        path = request.path
        return TemplateResponse(request, 'game/waiting_room.html', { "type": path.split('/')[-1] })
    
class GamePlayView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, game_id=None):
        user = request.user
        if not game_id or not game_rooms.get('game_' + game_id):
            notificationManager.add_notification(user, 'There is no game like that.', {"path": "/"}, 'redirection', False)
            return redirect('/')
        isMultiplayer = game_rooms['game_' + game_id]['game'].get_is_multiplayer()
        isTournament = game_rooms['game_' + game_id]['game'].is_game_tournament()
        if isMultiplayer and not isTournament:
            friend_dict = getFriends(request.user)
        else:
            friend_dict = {}
        return TemplateResponse(request, 'game/play.html', {'game': { "id": game_id }, "render_friends": {
            "render": isMultiplayer and not isTournament,
            "friends": friend_dict
        }})
        
class GameInviteView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, game_id, username):
        try:
            room = getFriendChatRooms(request.user, username)
            if not room:
                response = genResponse(False, "User not found", None)
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            # send game invite
            target_user = User.objects.get(username=username)
            notificationManager.add_notification(target_user.id, 'Game invite', {"game_id": game_id}, 'match_invite', True)
            ChatMessages(room=room, sender=request.user, message='Game invite', type='match_invite', payload={"game_id": game_id}).save()
            response = genResponse(True, "Game joined successfully", None)
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            response = genResponse(False, str(e), None)
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

class GameCreateView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serilizer = GameCreationSerilizer(data=request.data)
            if serilizer.is_valid():
                user = request.user
                data = serilizer.validated_data
                game_id = generateRandomID('gamerecords')
                game_record = GameRecords.objects.create(game_id=game_id, player1_score=0, player2_score=0, winner_id=None, total_match_time=0)
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
