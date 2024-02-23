from django.contrib import admin
from .models import CustomUserManager, CustomUser


admin.site.register(CustomUser)