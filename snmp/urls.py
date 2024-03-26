from django.urls import path
# from . import views
from .views.switch_views import *
from .views.dashboard_views import *
from .views.update_views import *

urlpatterns = [
    path('', switches, name='switches'),
    path('switches/', switches, name='switches'),
    path('switches/create/', switch_create, name='switch_create'),
    path('switches/<int:pk>/', switch_detail, name='switch_detail'),
    path('switches/<int:pk>/update/', switch_update, name='switch_update'),
    path('switches/<int:pk>/delete/', switch_delete, name='switch_delete'),
    path('switches/switch_status/<int:pk>/', switch_status, name='switch_status'),
    path('switches/update_optical_info/<int:pk>/', update_optical_info, name='update_optical_info'),
    path('switches/neighbor-switches-map/', neighbor_switches_map, name='neighbor_switches_map'),
    path('switches/offline/', switches_offline, name='offline'),
    path('switches/switches_high_sig/', switches_high_sig, name='switches_high_sig'),
    path('switches/switches_high_sig_15/', switches_high_sig_15, name='switches_high_sig_15'),
    path('switches/switches_high_sig_10/', switches_high_sig_10, name='switches_high_sig_10'),
    path('dashboard/', switches_updown, name='dashboard'),
    path('switches/update_switch_ports_data/<int:pk>/', update_switch_ports_data, name='update_switch_ports_data'),
    path('switches/update_switch_inventory/<int:pk>/', update_switch_inventory, name='update_switch_inventory')

    # path('switches/online_switches/', views.online_switches, name='online_switches'),
]