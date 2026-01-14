"""
API views for user authentication and management.
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

from users.api.serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    PasswordChangeSerializer,
)
from users.models import UserProfile

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token view with additional user info."""
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """API view for user registration."""
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer


class PasswordChangeView(generics.UpdateAPIView):
    """API view for password change."""
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Password updated successfully'
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Get current authenticated user info."""
    try:
        profile = request.user.userprofile
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'profile': {
                'id': profile.id,
                'phone': profile.phone,
                'position': profile.position,
                'department': profile.department,
                'avatar': request.build_absolute_uri(profile.avatar.url) if profile.avatar else None,
            }
        })
    except UserProfile.DoesNotExist:
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'profile': None,
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout user (client should delete token)."""
    return Response({
        'message': 'Successfully logged out. Please delete your token.'
    }, status=status.HTTP_200_OK)
