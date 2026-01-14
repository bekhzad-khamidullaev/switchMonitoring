"""SNMP app URL configuration.

This package is the canonical `snmp.urls` module.
It includes:
- Flowbite frontend pages
- Existing legacy SNMP views
- API routes under /snmp/api/
"""

from django.urls import path, include

from snmp.views.switch_views import *  # noqa: F403
from snmp.views.dashboard_views import *  # noqa: F403
from snmp.views.update_views import *  # noqa: F403
from snmp.views.requests_views import *  # noqa: F403
from snmp.views.export import *  # noqa: F403
from snmp.views.tree_views import monitoring_tree_view


urlpatterns = [
    # Flowbite Frontend
    path('', include('snmp.flowbite_urls')),

    # Original URLs
    path('monitoring/', monitoring_tree_view, name='monitoring_tree_view'),
    path('api/', include('snmp.api.urls')),

    path('', switches, name='switches'),  # noqa: F405
    path('switches/', switches, name='switches'),  # noqa: F405
    path('switches/create/', switch_create, name='switch_create'),  # noqa: F405
    path('switches/<int:pk>/', switch_detail, name='switch_detail'),  # noqa: F405
    path('switches/<int:pk>/update/', switch_update, name='switch_update'),  # noqa: F405
    path('switch/<int:pk>/delete/', switch_delete, name='switch_delete'),  # noqa: F405
    path('switches/<int:pk>/confirm_delete/', switch_confirm_delete, name='switch_confirm_delete'),  # noqa: F405
    path('switches/switch_status/<int:pk>/', switch_status, name='switch_status'),  # noqa: F405
    path('switches/update_optical_info/<int:pk>/', update_optical_info, name='update_optical_info'),  # noqa: F405
    path('switches/neighbor-switches-map/', neighbor_switches_map, name='neighbor_switches_map'),  # noqa: F405
    path('switches/offline/', switches_offline, name='offline'),  # noqa: F405
    path('switches/switches_high_sig/', switches_high_sig, name='switches_high_sig'),  # noqa: F405
    path('switches/switches_high_sig_15/', switches_high_sig_15, name='switches_high_sig_15'),  # noqa: F405
    path('switches/switches_high_sig_10/', switches_high_sig_10, name='switches_high_sig_10'),  # noqa: F405
    path('switches/switches_high_sig_11/', switches_high_sig_11, name='switches_high_sig_11'),  # noqa: F405
    path('dashboard/', switches_updown, name='dashboard'),  # noqa: F405
    path('switches/update_switch_ports_data/<int:pk>/', update_switch_ports_data, name='update_switch_ports_data'),  # noqa: F405
    path('switches/update_switch_inventory/<int:pk>/', update_switch_inventory, name='update_switch_inventory'),  # noqa: F405
    path('switches/synch_zbx/', sync_hosts_from_zabbix, name='sync_zbx'),  # noqa: F405
    path('switches/export/high_sig', export_high_sig_switches_to_excel, name='export_high_sig_switches_to_excel'),  # noqa: F405
    path('switches/export/optical_ports', export_optical_ports_to_excel, name='export_optical_ports_to_excel'),  # noqa: F405
]
