from django.urls import path
from . import views

urlpatterns = [
    path('switches/', views.switches, name='switches'),
    path('switches/create/', views.switch_create, name='switch_create'),
    path('switches/<int:pk>/', views.switch_detail, name='switch_detail'),
    path('switches/<int:pk>/update/', views.switch_update, name='switch_update'),
    path('switches/<int:pk>/delete/', views.switch_delete, name='switch_delete'),
    path('switches/switch_status/<int:pk>/', views.switch_status, name='switch_status'),
    path('switches/update_optical_info/<int:pk>/', views.update_optical_info, name='update_optical_info'),
    path('switches/neighbor-switches-map/', views.neighbor_switches_map, name='neighbor_switches_map'),
    path('switches/offline/', views.switches_offline, name='offline'),
    path('switches/switches_high_sig/', views.switches_high_sig, name='switches_high_sig'),
    path('dashboard/', views.switches_updown, name='dashboard'),
    path('switches/update_switch_ports_data/<int:pk>/', views.update_switch_ports_data, name='update_switch_ports_data'),
    path('switches/update_switch_inventory/<int:pk>/', views.update_switch_inventory, name='update_switch_inventory')

    # path('switches/online_switches/', views.online_switches, name='online_switches'),
]