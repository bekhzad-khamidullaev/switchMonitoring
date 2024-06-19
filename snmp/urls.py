from django.urls import path
# from . import views
from .views.switch_views import *
from .views.dashboard_views import *
from .views.update_views import *
from .views.requests_views import *
from .views.export import *
    
urlpatterns = [
    path('', switches, name='switches'),
    path('switches/', switches, name='switches'),
    path('switches/create/', switch_create, name='switch_create'),
    path('switches/<int:pk>/', switch_detail, name='switch_detail'),
    path('switches/<int:pk>/update/', switch_update, name='switch_update'),
    path('switch/<int:pk>/delete/', switch_delete, name='switch_delete'),
    path('switches/<int:pk>/confirm_delete/', switch_confirm_delete, name='switch_confirm_delete'),
    path('switches/switch_status/<int:pk>/', switch_status, name='switch_status'),
    path('switches/update_optical_info/<int:pk>/', update_optical_info, name='update_optical_info'),
    path('switches/neighbor-switches-map/', neighbor_switches_map, name='neighbor_switches_map'),
    path('switches/offline/', switches_offline, name='offline'),
    path('switches/switches_high_sig/', switches_high_sig, name='switches_high_sig'),
    path('switches/switches_high_sig_15/', switches_high_sig_15, name='switches_high_sig_15'),
    path('switches/switches_high_sig_10/', switches_high_sig_10, name='switches_high_sig_10'),
    path('switches/switches_high_sig_11/', switches_high_sig_11, name='switches_high_sig_11'),
    path('dashboard/', switches_updown, name='dashboard'),
    path('switches/update_switch_ports_data/<int:pk>/', update_switch_ports_data, name='update_switch_ports_data'),
    path('switches/update_switch_inventory/<int:pk>/', update_switch_inventory, name='update_switch_inventory'),
    path('switches/synch_zbx/', sync_hosts_from_zabbix, name='sync_zbx'),
    path('switches/export/high_sig', export_high_sig_switches_to_excel, name='export_high_sig_switches_to_excel'),

    # path('switches/online_switches/', views.online_switches, name='online_switches'),
]