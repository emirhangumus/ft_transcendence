from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Accounts, ChatMessages, ChatRooms, ChatUsers
from .queries.chat import assignChatbotRoom

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
        elif action == 'reject':
            # delete the friendship
            friendship = target.friendships_sender_set.get(receiver=user)
            friendship.delete()
        elif action == 'cancel':
            friendship = user.friendships_sender_set.get(receiver=target)
            friendship.status = 'rejected'
            friendship.save()
        return friendship
    