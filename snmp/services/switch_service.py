"""
Service layer for Switch-related business logic.
"""
from typing import List, Optional, Dict, Any, Tuple
from django.db.models import QuerySet, Q
from django.core.paginator import Paginator, Page
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache

from ..models import Switch, Branch, SwitchModel
from .base_service import BaseService
from .snmp_service import SNMPService


class SwitchService(BaseService):
    """
    Service for handling Switch-related business logic.
    """
    
    def __init__(self):
        super().__init__()
        self.snmp_service = SNMPService()
    
    def get_switches_for_user(self, user: User, search_query: str = None) -> QuerySet:
        """
        Get switches filtered by user permissions and optional search query.
        """
        try:
            # Get user permitted branches (existing logic from views)
            from ..views.qoshimcha import get_permitted_branches
            user_permitted_branches = get_permitted_branches(user)
            
            queryset = Switch.objects.filter(
                branch__in=user_permitted_branches
            ).select_related('model', 'model__vendor', 'branch', 'ats').order_by('-pk')
            
            if search_query:
                queryset = self._apply_search_filter(queryset, search_query)
            
            self.log_info(f"Retrieved {queryset.count()} switches for user {user.username}")
            return queryset
            
        except Exception as e:
            self.log_error(f"Error getting switches for user {user.username}: {e}")
            return Switch.objects.none()
    
    def _apply_search_filter(self, queryset: QuerySet, search_query: str) -> QuerySet:
        """Apply search filter to switch queryset."""
        return queryset.filter(
            Q(pk__icontains=search_query) |
            Q(model__vendor__name__icontains=search_query) |
            Q(hostname__icontains=search_query) |
            Q(ip__icontains=search_query) |
            Q(model__device_model__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(sfp_vendor__icontains=search_query) |
            Q(part_number__icontains=search_query) |
            Q(rx_signal__icontains=search_query) |
            Q(tx_signal__icontains=search_query)
        )
    
    def get_paginated_switches(self, user: User, page_number: int = 1, 
                             page_size: int = 25, search_query: str = None) -> Page:
        """
        Get paginated switches for a user.
        """
        try:
            switches = self.get_switches_for_user(user, search_query)
            paginator = Paginator(switches, page_size)
            page = paginator.get_page(page_number)
            
            self.log_info(f"Retrieved page {page_number} of switches for user {user.username}")
            return page
            
        except Exception as e:
            self.log_error(f"Error getting paginated switches: {e}")
            # Return empty page on error
            paginator = Paginator(Switch.objects.none(), page_size)
            return paginator.get_page(1)
    
    def create_switch(self, switch_data: Dict[str, Any]) -> Tuple[Optional[Switch], Optional[str]]:
        """
        Create a new switch with validation and auto-discovery.
        """
        try:
            # Validate required fields
            if not switch_data.get('ip') or not switch_data.get('hostname'):
                return None, "IP address and hostname are required"
            
            # Check if switch already exists
            existing = Switch.objects.filter(
                Q(ip=switch_data['ip']) | Q(hostname=switch_data['hostname'])
            ).first()
            
            if existing:
                return None, f"Switch with IP {switch_data['ip']} or hostname {switch_data['hostname']} already exists"
            
            # Create switch
            switch, error = self.safe_create(Switch, **switch_data)
            if error:
                return None, error
            
            # Auto-discover switch information
            self.auto_discover_switch_info(switch)
            
            return switch, None
            
        except Exception as e:
            error_msg = f"Error creating switch: {e}"
            self.log_error(error_msg)
            return None, error_msg
    
    def update_switch(self, switch: Switch, update_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Update switch with validation.
        """
        try:
            # Remove empty values
            clean_data = {k: v for k, v in update_data.items() if v is not None}
            
            success, error = self.safe_update(switch, **clean_data)
            if success:
                # Clear cache for this switch
                cache.delete(f'switch_status_{switch.id}')
            
            return success, error
            
        except Exception as e:
            error_msg = f"Error updating switch {switch.id}: {e}"
            self.log_error(error_msg)
            return False, error_msg
    
    def auto_discover_switch_info(self, switch: Switch) -> Dict[str, Any]:
        """
        Auto-discover switch information via SNMP.
        """
        try:
            self.log_info(f"Starting auto-discovery for switch {switch.hostname} ({switch.ip})")
            
            result = {
                'success': False,
                'discovered_data': {},
                'errors': []
            }
            
            # Get SNMP client
            snmp_client = self.snmp_service.get_snmp_client(
                switch.ip, 
                switch.snmp_community_ro
            )
            
            if not snmp_client:
                result['errors'].append("Could not establish SNMP connection")
                return result
            
            # Discover basic system information
            discovered_data = {}
            
            # System description
            sys_descr = self.snmp_service.get_system_description(snmp_client)
            if sys_descr:
                discovered_data['system_description'] = sys_descr
                
                # Try to match switch model based on description
                model = self._match_switch_model(sys_descr)
                if model:
                    discovered_data['model'] = model
            
            # System uptime
            uptime = self.snmp_service.get_system_uptime(snmp_client)
            if uptime:
                discovered_data['uptime'] = uptime
            
            # Update switch with discovered data
            if discovered_data:
                success, error = self.safe_update(switch, **discovered_data)
                if success:
                    result['success'] = True
                    result['discovered_data'] = discovered_data
                    self.log_info(f"Auto-discovery completed for switch {switch.hostname}")
                else:
                    result['errors'].append(f"Failed to update switch: {error}")
            else:
                result['errors'].append("No data could be discovered")
            
            return result
            
        except Exception as e:
            error_msg = f"Error in auto-discovery for switch {switch.id}: {e}"
            self.log_error(error_msg)
            return {
                'success': False,
                'discovered_data': {},
                'errors': [error_msg]
            }
    
    def _match_switch_model(self, system_description: str) -> Optional[SwitchModel]:
        """
        Try to match switch model based on system description.
        """
        try:
            # Simple matching logic - can be enhanced
            description_lower = system_description.lower()
            
            # Look for known vendors/models in description
            models = SwitchModel.objects.select_related('vendor').all()
            
            for model in models:
                if (model.vendor.name.lower() in description_lower and 
                    model.device_model.lower() in description_lower):
                    return model
            
            return None
            
        except Exception as e:
            self.log_error(f"Error matching switch model: {e}")
            return None
    
    def get_switch_statistics(self, user: User) -> Dict[str, Any]:
        """
        Get switch statistics for dashboard.
        """
        try:
            switches = self.get_switches_for_user(user)
            
            stats = {
                'total_switches': switches.count(),
                'online_switches': switches.filter(status=True).count(),
                'offline_switches': switches.filter(status=False).count(),
                'high_signal_switches': switches.filter(
                    Q(rx_signal__gt=-15) | Q(tx_signal__gt=-15)
                ).count(),
                'by_vendor': {},
                'by_branch': {},
                'recent_updates': switches.filter(
                    last_update__gte=timezone.now() - timezone.timedelta(hours=24)
                ).count()
            }
            
            # Calculate offline percentage
            if stats['total_switches'] > 0:
                stats['offline_percentage'] = round(
                    (stats['offline_switches'] / stats['total_switches']) * 100, 2
                )
            else:
                stats['offline_percentage'] = 0
            
            # Group by vendor
            vendor_counts = switches.values('model__vendor__name').distinct()
            for vendor in vendor_counts:
                if vendor['model__vendor__name']:
                    count = switches.filter(model__vendor__name=vendor['model__vendor__name']).count()
                    stats['by_vendor'][vendor['model__vendor__name']] = count
            
            # Group by branch
            branch_counts = switches.values('branch__name').distinct()
            for branch in branch_counts:
                if branch['branch__name']:
                    count = switches.filter(branch__name=branch['branch__name']).count()
                    stats['by_branch'][branch['branch__name']] = count
            
            self.log_info(f"Generated statistics for user {user.username}")
            return stats
            
        except Exception as e:
            self.log_error(f"Error getting switch statistics: {e}")
            return {
                'total_switches': 0,
                'online_switches': 0,
                'offline_switches': 0,
                'high_signal_switches': 0,
                'offline_percentage': 0,
                'by_vendor': {},
                'by_branch': {},
                'recent_updates': 0
            }