from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.db import models

class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('The username field must be set')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(username, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=15, unique=True)
    username = models.CharField(max_length=30, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    is_view_only_user = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set',
        related_query_name='customuser',
        blank=True,
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_set',
        related_query_name='customuser',
        blank=True,
    )
    

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        # Allow superusers access to all permissions
        if self.is_superuser:
            return True

        # Allow moderators access to specific permission
        if self.is_moderator and perm == "snmp.switch":
            return True

        return False

    def has_module_perms(self, app_label):
        # Allow superusers access to all modules
        if self.is_superuser:
            return True

        # Allow moderators access to specific module
        if self.is_moderator and app_label == "snmp":
            return True

        return False



    class Meta:
        permissions = [
            ("change_custommodel", "Can change Custom Model"),
            # Add other permissions if needed
        ]