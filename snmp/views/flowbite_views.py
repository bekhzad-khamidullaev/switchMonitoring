"""Flowbite frontend views.

JWT approach (Option 2): pages are rendered without Django session auth.
The frontend uses JWT tokens (stored in localStorage) to access the API.
"""

from django.shortcuts import render, get_object_or_404

from snmp.models import Switch


def login_view(request):
    return render(request, 'login_flowbite.html')


def dashboard_view(request):
    return render(request, 'dashboard_flowbite.html')


def switch_list_view(request):
    return render(request, 'switches_list_flowbite.html')


def switch_detail_view(request, switch_id):
    # We only need id in template; data loads via API.
    _ = get_object_or_404(Switch, id=switch_id)
    return render(request, 'switch_detail_flowbite.html', {'switch_id': switch_id})


def ports_monitoring_view(request):
    return render(request, 'ports_monitoring_flowbite.html')


def topology_view(request):
    return render(request, 'topology_flowbite.html')


def analytics_view(request):
    return render(request, 'analytics_flowbite.html')


def ats_view(request):
    return render(request, 'ats_flowbite.html')


def host_groups_view(request):
    return render(request, 'host_groups_flowbite.html')


def switch_models_view(request):
    return render(request, 'switch_models_flowbite.html')


def neighbors_view(request):
    return render(request, 'neighbors_flowbite.html')


def bandwidth_view(request):
    return render(request, 'bandwidth_flowbite.html')


def vendors_view(request):
    return render(request, 'vendors_flowbite.html')


def branches_view(request):
    return render(request, 'branches_flowbite.html')


def settings_view(request):
    return render(request, 'settings_flowbite.html')


def account_view(request):
    return render(request, 'account_flowbite.html')
