from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from django.contrib.auth.models import User
from .serializers import UserSerializer, LoginSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import render
from .utils import genResponse
from rest_framework.permissions import AllowAny, IsAuthenticated

# Create your views here.
class HomeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return render(request, 'home.html')

class RegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    
    def get(self, request):
        return render(request, 'register.html')
    
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
        return render(request, 'login.html')
    
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