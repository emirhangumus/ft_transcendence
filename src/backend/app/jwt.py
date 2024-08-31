from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework.exceptions import AuthenticationFailed

class PingPongObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['email'] = user.email
        token['username'] = user.username
        # ...

        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({
            'email': self.user.email,
            'username': self.user.username,
            # ...
        })
        return data
    
def validate_access_token(token):
    try:
        # Decode and validate the token
        access_token = AccessToken(token)
        
        # If no exception is raised, the token is valid
        return {
            'valid': True,
            'user_id': access_token['user_id'],
            'username': access_token['username'],
            'email': access_token['email']
        }
    except (AuthenticationFailed, Exception) as e:
        # Handle token validation errors
        return {
            'valid': False,
            'error': str(e)
        }

def validate_refresh_token(token):
    try:
        # Decode and validate the token
        refresh_token = RefreshToken(token)
        
        # If no exception is raised, the token is valid
        return {
            'valid': True,
            'user_id': refresh_token['user_id'],
            'username': refresh_token['username'],
            'email': refresh_token['email']
        }
    except (AuthenticationFailed, Exception) as e:
        # Handle token validation errors
        return {
            'valid': False,
            'error': str(e)
        }