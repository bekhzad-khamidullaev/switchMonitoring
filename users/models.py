from django.contrib.auth.models import User, Group
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import json
import uuid

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(max_length=500, null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)
    social_media_links = models.URLField(max_length=200, null=True, blank=True)
    preferences_theme = models.CharField(max_length=50, null=True, blank=True)
    preferences_notifications = models.BooleanField(default=True)
    preferences_language = models.CharField(max_length=20, null=True, blank=True)
    last_login = models.DateTimeField(auto_now=True, null=True, blank=True)
    last_active = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    api_token = models.CharField(max_length=128, null=True, blank=True)
    
    def update_last_active(self):
        self.last_active = timezone.now()
        self.save()

    def generate_api_token(self):
        import hashlib
        raw_token = str(uuid.uuid4())
        # Store a fast hash (SHA-256) instead of slow PBKDF2
        self.api_token = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        self.save()
        return raw_token

    def verify_api_token(self, raw_token):
        if not self.api_token or not raw_token:
            return False
        import hashlib
        hashed_token = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        # Fallback to check_password to support existing legacy tokens during transition
        if self.api_token.startswith('pbkdf2_'):
            return check_password(raw_token, self.api_token)
        return hashed_token == self.api_token

    def export_data(self):
        user_data = {
            'username': self.user.username,
            'email': self.user.email,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'bio': self.bio,
        }
        return json.dumps(user_data)

    def __str__(self):
        return self.user.username

    def set_role(self, role_name):
        group, _ = Group.objects.get_or_create(name=role_name)
        self.user.groups.add(group)

    def remove_role(self, role_name):
        try:
            group = Group.objects.get(name=role_name)
            self.user.groups.remove(group)
        except Group.DoesNotExist:
            pass

    def has_role(self, role_name):
        return self.user.groups.filter(name=role_name).exists()
