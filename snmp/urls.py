from django.urls import path, include
from .views.switch_views import *
from .views.dashboard_views import *
from .views.update_views import *
from .views.requests_views import *
from .views.export import *
from .views.monitoring_views import *

# Switch management URLs    
urlpatterns = [
    # Main dashboard
    path('', switches, name='switches'),
    
    # Switch CRUD operations
    path('switches/', switches, name='switches'),
    path('switches/create/', switch_create, name='switch_create'),
    path('switches/<int:pk>/', switch_detail, name='switch_detail'),
    path('switches/<int:pk>/update/', switch_update, name='switch_update'),
    path('switch/<int:pk>/delete/', switch_delete, name='switch_delete'),
    path('switches/<int:pk>/confirm_delete/', switch_confirm_delete, name='switch_confirm_delete'),
    
    # Switch operations
    path('switches/switch_status/<int:pk>/', switch_status, name='switch_status'),
    path('switches/update_optical_info/<int:pk>/', update_optical_info, name='update_optical_info'),
    path('switches/update_switch_ports_data/<int:pk>/', update_switch_ports_data, name='update_switch_ports_data'),
    path('switches/update_switch_inventory/<int:pk>/', update_switch_inventory, name='update_switch_inventory'),
    
    # Switch filtering views
    path('switches/offline/', switches_offline, name='offline'),
    path('switches/switches_high_sig/', switches_high_sig, name='switches_high_sig'),
    path('switches/switches_high_sig_15/', switches_high_sig_15, name='switches_high_sig_15'),
    path('switches/switches_high_sig_10/', switches_high_sig_10, name='switches_high_sig_10'),
    path('switches/switches_high_sig_11/', switches_high_sig_11, name='switches_high_sig_11'),
    
    # Dashboard and visualization
    path('dashboard/', switches_updown, name='dashboard'),
    path('switches/neighbor-switches-map/', neighbor_switches_map, name='neighbor_switches_map'),
    
    # Monitoring and health checks
    path('monitoring/', monitoring_dashboard, name='monitoring_dashboard'),
    path('health-check/', health_check_view, name='health_check'),
    path('metrics/', metrics_view, name='metrics'),
    path('monitoring/export-health/', export_health_report, name='export_health_report'),
    
    # AJAX endpoints
    path('ajax/switch-status/<int:switch_id>/', ajax_switch_status, name='ajax_switch_status'),
    path('ajax/system-stats/', ajax_system_stats, name='ajax_system_stats'),
    
    # Integration and export
    path('switches/synch_zbx/', sync_hosts_from_zabbix, name='sync_zbx'),
    path('switches/export/high_sig/', export_high_sig_switches_to_excel, name='export_high_sig_switches_to_excel'),
]