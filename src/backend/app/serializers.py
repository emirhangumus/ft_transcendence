from rest_framework import serializers
from django.contrib.auth.models import User

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