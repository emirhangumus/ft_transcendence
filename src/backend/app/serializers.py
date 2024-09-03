from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Accounts, ChatMessages, ChatRooms, ChatUsers, GameRecords, GameStats
from .queries.chat import assignChatbotRoom, createChatRoom, leaveChatRoom

class GameStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameStats
        fields = ['stats']

class GameRecordSerializer(serializers.ModelSerializer):
    stats = GameStatsSerializer(source='gamestats_set', many=True, read_only=True)

    class Meta:
        model = GameRecords
        fields = ['game_id', 'player1_score', 'player2_score', 'winner_id', 'total_match_time', 'tournament_id', 'created_at', 'stats']

class ChangeProfileSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30, required=True)
    first_name = serializers.CharField(max_length=30, required=True)
    last_name = serializers.CharField(max_length=30, required=True)
    email = serializers.EmailField(max_length=128, required=True)
    bio = serializers.CharField(max_length=256, required=True)
    profile_picture_url = serializers.URLField(max_length=256, required=True)

    def validate(self, data):
        username = data.get('username')
        email = data.get('email')
        if username and email:
            if not User.objects.filter(username=username).exists():
                if not User.objects.filter(email=email).exists():
                    return data
                else:
                    raise serializers.ValidationError("Email already exists")
            else:
                raise serializers.ValidationError("Username already exists")
        else:
            raise serializers.ValidationError("Invalid data")

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['bio', 'profile_picture_url', 'status', 'updated_at', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=30, required=True)
    last_name = serializers.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'password')

    def create(self, validated_data):
        username = validated_data['username']
        password = validated_data['password']
        email = validated_data['email']
        first_name = validated_data['first_name']
        last_name = validated_data['last_name']  
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )
        account = Accounts.objects.create(id=user)
        assignChatbotRoom(account.id)
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=128, required=True)
    password = serializers.CharField(max_length=128, required=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        if email and password:
            user = User.objects.filter(email=email).first()
            if user:
                if user.check_password(password):
                    return data
                else:
                    raise serializers.ValidationError("Invalid credentials 3")
            else:
                raise serializers.ValidationError("Invalid credentials 2")
        else:
            raise serializers.ValidationError("Invalid credentials 1")
        
class FriendRequestActionsSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=10, required=True)
    username = serializers.CharField(max_length=30, required=True)
    
    def validate(self, data):
        action = data.get('action')
        target = data.get('username')
        
        if target:
            if User.objects.filter(username=target).exists():
                target = User.objects.get(username=target)
                if action == 'accept':
                    if target.friendships_sender_set.filter(receiver=self.context['request'].user, status='pending').exists():
                        return data
                    else:
                        raise serializers.ValidationError("Friend request not found")
                elif action == 'reject':
                    if target.friendships_sender_set.filter(receiver=self.context['request'].user, status='pending').exists():
                        return data
                    else:
                        raise serializers.ValidationError("Friend request not found")
                elif action == 'cancel':
                    if self.context['request'].user.friendships_sender_set.filter(receiver=target, status='pending').exists():
                        return data
                    else:
                        raise serializers.ValidationError("Friend request not found")
                elif action == 'remove':
                    if self.context['request'].user.friendships_sender_set.filter(receiver=target).exists() or self.context['request'].user.friendships_receiver_set.filter(sender=target).exists():
                        return data
                    else:
                        raise serializers.ValidationError("Friend request not found")
                else:
                    raise serializers.ValidationError("Invalid action")
        else:
            raise serializers.ValidationError("Invalid target")
        
    def update(self, instance, validated_data):
        action = validated_data['action']
        target = validated_data['username']
        user = self.context['request'].user
        
        target = User.objects.get(username=target)
        
        if action == 'accept':
            friendship = target.friendships_sender_set.get(receiver=user)
            friendship.status = 'accepted'
            friendship.save()
            createChatRoom(f"{user.username}-{target.username}", user, [target.username], can_leave=False)
        elif action == 'reject':
            # delete the friendship
            friendship = target.friendships_sender_set.get(receiver=user)
            friendship.delete()
        elif action == 'cancel':
            friendship = user.friendships_sender_set.get(receiver=target)
            friendship.status = 'rejected'
            friendship.save()
        elif action == 'remove':
            try:
                friendship = user.friendships_sender_set.get(receiver=target)
            except Exception:
                friendship = target.friendships_sender_set.get(receiver=user)
                pass

            if friendship:
                friendship.delete()
                # find the chat room and delete it
                chatroom = ChatRooms.objects.filter(name=f"{user.username}-{target.username}", can_leave=False).first()
                if chatroom:
                    leaveChatRoom(chatroom.id, user.id)
        return friendship
    

class GameCreationSerilizer(serializers.Serializer):
    ball_color = serializers.CharField(max_length=7, required=True)
    map_width = serializers.IntegerField(required=True)
    map_height = serializers.IntegerField(required=True)
    background_color = serializers.CharField(max_length=7, required=True)
    
    skill_ball_freeze = serializers.BooleanField(required=True)
    skill_ball_speed = serializers.BooleanField(required=True)
    
    powerup_slow_down_opponent = serializers.BooleanField(required=True)
    powerup_speed_up_yourself = serializers.BooleanField(required=True)
    powerup_revert_opponent_controls = serializers.BooleanField(required=True)
    
    room_type = serializers.CharField(max_length=12, required=True)
    
    def validate(self, data):
        width = data['map_width']
        height = data['map_height']
        if width and height:
            if 500 <= int(width) <= 2000 and 500 <= int(height) <= 2000:
                return data
            else:
                raise serializers.ValidationError("Invalid map size")
        else:
            raise serializers.ValidationError("Invalid data")
        
class TournamentSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, required=True)
    player_amount = serializers.IntegerField(required=True)
    
    def validate(self, data):
        player_amount = data['player_amount']
        if player_amount:
            # player amount must be power of 4 and max 32
            if 4 <= player_amount <= 32 and player_amount & (player_amount - 1) == 0:
                return data
            else:
                raise serializers.ValidationError("Invalid player amount. Must be power of 4 and max 32")
        else:
            raise serializers.ValidationError("Invalid data")