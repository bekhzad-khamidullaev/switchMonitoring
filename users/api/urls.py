"""
URLs for user authentication API.
"""
from django.urls import path
from users.api.views import (
    CustomTokenObtainPairView,
    UserRegistrationView,
    PasswordChangeView,
    current_user,
    logout,
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('me/', current_user, name='current-user'),
    path('password/change/', PasswordChangeView.as_view(), name='password-change'),
    path('logout/', logout, name='logout'),
]
