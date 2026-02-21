from django.urls import include, path

from snmp.api.urls import urlpatterns as api_urlpatterns
from snmp.web.views.dashboard import devices_updown, neighbor_devices_map, neighbor_devices_map_data
from snmp.web.views.device_operations import (
    devices_high_signal_10,
    devices_high_signal_11,
    devices_high_signal_15,
    devices_high_signal_20,
    devices_offline,
    refresh_device_inventory,
    update_device_ports_data,
    update_optical_info,
)
from snmp.web.views.devices import (
    device_confirm_delete,
    device_create,
    device_delete,
    device_detail,
    device_host_settings,
    device_status,
    device_update,
    devices,
)
from snmp.web.views.exports import export_low_signal_devices_to_excel, port_activity_report
from snmp.web.views.integrations import run_bulk_device_job, sync_hosts_from_zabbix
from snmp.web.views.metrics import (
    device_metrics,
    export_device_metrics_csv,
    update_metric_subscription,
)
from snmp.web.views.profiles import (
    device_profile_create,
    device_profile_delete,
    device_profile_detail,
    device_profile_update,
    device_profiles,
)

urlpatterns = [
    path('', devices, name='devices'),
    path('devices/', devices, name='devices'),
    path('devices/create/', device_create, name='device_create'),
    path('devices/<int:pk>/', device_detail, name='device_detail'),
    path('devices/<int:pk>/update/', device_update, name='device_update'),
    path('devices/<int:pk>/host-settings/', device_host_settings, name='device_host_settings'),
    path('devices/<int:pk>/delete/', device_delete, name='device_delete'),
    path('devices/<int:pk>/confirm_delete/', device_confirm_delete, name='device_confirm_delete'),
    path('devices/<int:pk>/status/', device_status, name='device_status'),
    path('devices/<int:pk>/optics/update/', update_optical_info, name='update_optical_info'),
    path('devices/network-map/', neighbor_devices_map, name='neighbor_devices_map'),
    path('devices/network-map/data/', neighbor_devices_map_data, name='neighbor_devices_map_data'),
    path('devices/offline/', devices_offline, name='devices_offline'),
    path('devices/signals/high-20/', devices_high_signal_20, name='devices_high_signal_20'),
    path('devices/signals/high-15/', devices_high_signal_15, name='devices_high_signal_15'),
    path('devices/signals/high-10/', devices_high_signal_10, name='devices_high_signal_10'),
    path('devices/signals/high-11/', devices_high_signal_11, name='devices_high_signal_11'),
    path('dashboard/', devices_updown, name='dashboard'),
    path('devices/<int:pk>/ports/update/', update_device_ports_data, name='update_device_ports_data'),
    path('devices/<int:pk>/inventory/update/', refresh_device_inventory, name='refresh_device_inventory'),
    path('devices/sync/zabbix/', sync_hosts_from_zabbix, name='sync_zbx'),
    path('devices/jobs/bulk/', run_bulk_device_job, name='run_bulk_device_job'),
    path('devices/export/low-signal/', export_low_signal_devices_to_excel, name='export_low_signal_devices_to_excel'),
    path('devices/reports/port-activity/', port_activity_report, name='port_activity_report'),
    path('devices/<int:pk>/metrics/', device_metrics, name='device_metrics'),
    path('profiles/', device_profiles, name='device_profiles'),
    path('profiles/create/', device_profile_create, name='device_profile_create'),
    path('profiles/<int:pk>/', device_profile_detail, name='device_profile_detail'),
    path('profiles/<int:pk>/edit/', device_profile_update, name='device_profile_update'),
    path('profiles/<int:pk>/delete/', device_profile_delete, name='device_profile_delete'),
    path('metrics/subscriptions/<int:subscription_id>/update/', update_metric_subscription, name='update_metric_subscription'),
    path('devices/<int:pk>/metrics/export.csv', export_device_metrics_csv, name='export_device_metrics_csv'),
    path('api/', include((api_urlpatterns, 'snmp_api'))),
]
