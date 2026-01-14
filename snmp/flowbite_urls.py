"""URLs for Flowbite frontend views (JWT auth in browser)."""

from django.urls import path

from snmp.views.flowbite_views import (
    analytics_view,
    account_view,
    ats_view,
    bandwidth_view,
    branches_view,
    dashboard_view,
    host_groups_view,
    login_view,
    neighbors_view,
    optical_monitoring_view,
    ports_monitoring_view,
    settings_view,
    switch_detail_view,
    switch_list_view,
    switch_models_view,
    topology_view,
    vendors_view,
)

urlpatterns = [
    # Start page (A): /snmp/ -> /snmp/login/
    path('', login_view, name='flowbite_start'),

    path('login/', login_view, name='flowbite_login'),
    path('dashboard/', dashboard_view, name='dashboard'),

    path('switches/', switch_list_view, name='switch_list'),
    path('switches/<int:switch_id>/', switch_detail_view, name='switch_detail'),

    path('ports/', ports_monitoring_view, name='ports_monitoring'),
    path('optical/', optical_monitoring_view, name='optical_monitoring'),
    path('topology/', topology_view, name='topology'),
    path('analytics/', analytics_view, name='analytics'),

    # Additional API resources coverage
    path('ats/', ats_view, name='ats'),
    path('host-groups/', host_groups_view, name='host_groups'),
    path('switch-models/', switch_models_view, name='switch_models'),
    path('vendors/', vendors_view, name='vendors'),
    path('neighbors/', neighbors_view, name='neighbors'),
    path('bandwidth/', bandwidth_view, name='bandwidth'),

    path('branches/', branches_view, name='branches'),
    path('settings/', settings_view, name='settings'),
    path('account/', account_view, name='account'),
]
