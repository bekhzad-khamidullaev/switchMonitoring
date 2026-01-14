"""
Custom permission classes for the SNMP API.
Implements role-based access control and object-level permissions.
"""
from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allows read access to any authenticated user.
    Write access only for admin users.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners or admins to edit.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Admin users have full access
        if request.user and request.user.is_staff:
            return True
        
        # Check if object has an owner field
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        return False


class CanManageSwitches(permissions.BasePermission):
    """
    Permission to manage switches.
    Requires specific permission or admin status.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('snmp.change_switch'))
        )


class CanManageNetwork(permissions.BasePermission):
    """
    Permission to manage network infrastructure (ATS, Branches, etc.).
    Requires admin status or specific permissions.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('snmp.change_branch'))
        )


class CanExecuteCommands(permissions.BasePermission):
    """
    Permission to execute commands on devices.
    Only for admin users or users with specific permission.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('snmp.can_execute_commands'))
        )


class CanViewSensitiveData(permissions.BasePermission):
    """
    Permission to view sensitive data like passwords, SNMP communities.
    Only for admin users.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class ReadOnlyPermission(permissions.BasePermission):
    """
    Read-only permission for specific views.
    """
    
    def has_permission(self, request, view):
        return (
            request.method in permissions.SAFE_METHODS and
            request.user and 
            request.user.is_authenticated
        )
