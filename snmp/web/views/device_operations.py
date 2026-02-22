import logging
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from snmp.models import Device, DeviceModel

from .access import (
    convert_uptime_to_human_readable,
    get_permitted_groups,
    user_can_access_device,
)

try:
    from ping3 import ping as ping_host
except Exception:  # pragma: no cover - optional dependency
    ping_host = None

logger = logging.getLogger("ICMP RESPONSE")

SNMP_COMMUNITY = settings.SNMP_DEFAULT_COMMUNITY_RO
OID_SYSTEM_HOSTNAME = 'iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME = 'iso.3.6.1.2.1.1.3.0'
OID_SYSTEM_DESCRIPTION = 'iso.3.6.1.2.1.1.1.0'


def _apply_device_search(queryset, search_query):
    if not search_query:
        return queryset
    return queryset.filter(
        Q(pk__icontains=search_query)
        | Q(vendor__icontains=search_query)
        | Q(device_type__vendor__name__icontains=search_query)
        | Q(hostname__icontains=search_query)
        | Q(ip__icontains=search_query)
        | Q(model__icontains=search_query)
        | Q(device_type__device_model__icontains=search_query)
        | Q(status__icontains=search_query)
        | Q(sfp_vendor__icontains=search_query)
        | Q(part_number__icontains=search_query)
        | Q(rx_signal__icontains=search_query)
        | Q(tx_signal__icontains=search_query)
    )


def _build_enriched_device_queryset(queryset):
    return (
        queryset.select_related('group', 'subgroup', 'device_type__vendor', 'profile')
        .annotate(
            metrics_subscriptions_total=Count('subscriptions', distinct=True),
            metrics_subscriptions_enabled=Count(
                'subscriptions',
                filter=Q(subscriptions__enabled=True),
                distinct=True,
            ),
            metrics_last_sample_ts=Max('subscriptions__samples__ts'),
        )
    )


def _render_filtered_device_list(request, *, template_name, page_items, title, subtitle, search_query):
    if request.headers.get('HX-Request') == 'true':
        return render(
            request,
            'partials/device_table.html',
            {
                'devices_page': page_items,
                'page_title': title,
                'page_subtitle': subtitle,
            },
        )
    return render(
        request,
        template_name,
        {
            'devices_page': page_items,
            'page_title': title,
            'page_subtitle': subtitle,
            'selected_search': search_query,
        },
    )


def refresh_device_status(device):
    ip_addr = str(device.ip) if device.ip else ''
    try:
        if not ip_addr:
            return JsonResponse({'error': 'Device IP is missing.'}, status=400)
        if ping_host is None:
            logger.warning('ping3 is not installed; cannot refresh device ICMP status')
            return JsonResponse({'error': 'ICMP backend is unavailable.'}, status=503)

        host_alive = ping_host(ip_addr, unit='ms', size=64, timeout=2)
        device.status = host_alive is not None
        device.save(update_fields=['status', 'updated'])
        return JsonResponse(
            {
                'status': 'UP' if device.status else 'DOWN',
                'alive': device.status,
                'rtt_ms': host_alive,
            }
        )
    except Exception as exc:
        logger.info('Error refreshing status for %s: %s', ip_addr, exc)
        return JsonResponse({'error': 'Failed to refresh device status.'}, status=500)


@login_required
@permission_required('snmp.change_device', raise_exception=True)
@require_POST
def update_optical_info(request, pk):
    from snmp.lib.update_port_info import SNMPUpdater

    device = get_object_or_404(Device, pk=pk)
    if not user_can_access_device(request.user, device):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        snmp_updater = SNMPUpdater(device, settings.SNMP_DEFAULT_COMMUNITY_RO)
        snmp_updater.update_switch_data()
        return JsonResponse(
            {
                'rx_signal': device.rx_signal,
                'tx_signal': device.tx_signal,
                'sfp_vendor': device.sfp_vendor,
                'part_number': device.part_number,
            }
        )
    except Exception:
        return JsonResponse({'error': 'An error occurred during SNMP update.'}, status=500)


@login_required
@permission_required('snmp.change_device', raise_exception=True)
@require_POST
def update_device_ports_data(request, pk):
    from snmp.lib.update_port_info import PortsInfo

    device = get_object_or_404(Device, pk=pk)
    if not user_can_access_device(request.user, device):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        port_info = PortsInfo()
        port_info.create_switch_ports(device)
        return JsonResponse({'message': 'Device port data updated successfully.'})
    except Exception as exc:
        return JsonResponse({'error': f'An error occurred during device port update: {exc}'}, status=500)


@login_required
def devices_offline(request):
    user_permitted_groups = get_permitted_groups(request.user)
    offline_items = Device.objects.filter(
        status=False,
        group__in=user_permitted_groups,
    )

    search_query = (request.GET.get('search') or '').strip()
    offline_items = _apply_device_search(offline_items, search_query)
    offline_items = _build_enriched_device_queryset(offline_items).order_by('subgroup')

    paginator = Paginator(offline_items, 25)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)
    return _render_filtered_device_list(
        request,
        template_name='device_list_offline.html',
        page_items=page_items,
        title='Offline Devices',
        subtitle='Devices currently unreachable',
        search_query=search_query,
    )


@login_required
def devices_high_signal_15(request):
    user_permitted_groups = get_permitted_groups(request.user)
    items = Device.objects.filter(
        rx_signal__lte=-15,
        rx_signal__gt=-20,
        group__in=user_permitted_groups,
    )

    search_query = (request.GET.get('search') or '').strip()
    items = _apply_device_search(items, search_query)
    items = _build_enriched_device_queryset(items).order_by('rx_signal')

    paginator = Paginator(items, 100)
    page_items = paginator.get_page(request.GET.get('page'))
    return _render_filtered_device_list(
        request,
        template_name='devices_high_sig_15.html',
        page_items=page_items,
        title='Signal from -20 to -15 dBm',
        subtitle='Degraded optical signal level',
        search_query=search_query,
    )


@login_required
def devices_high_signal_10(request):
    user_permitted_groups = get_permitted_groups(request.user)
    items = Device.objects.filter(
        rx_signal__lte=-11,
        rx_signal__gt=-15,
        group__in=user_permitted_groups,
    )

    search_query = (request.GET.get('search') or '').strip()
    items = _apply_device_search(items, search_query)
    items = _build_enriched_device_queryset(items).order_by('rx_signal')

    paginator = Paginator(items, 100)
    page_items = paginator.get_page(request.GET.get('page'))
    return _render_filtered_device_list(
        request,
        template_name='devices_high_sig_10.html',
        page_items=page_items,
        title='Signal from -15 to -11 dBm',
        subtitle='Warning optical signal level',
        search_query=search_query,
    )


@login_required
def devices_high_signal_20(request):
    user_permitted_groups = get_permitted_groups(request.user)
    items = Device.objects.filter(
        rx_signal__lte=-20,
        group__in=user_permitted_groups,
    )

    search_query = (request.GET.get('search') or '').strip()
    items = _apply_device_search(items, search_query)
    items = _build_enriched_device_queryset(items).order_by('rx_signal')

    paginator = Paginator(items, 25)
    page_items = paginator.get_page(request.GET.get('page'))
    return _render_filtered_device_list(
        request,
        template_name='devices_high_sig.html',
        page_items=page_items,
        title='Signal <= -20 dBm',
        subtitle='Critical optical signal level',
        search_query=search_query,
    )


@login_required
def devices_high_signal_11(request):
    user_permitted_groups = get_permitted_groups(request.user)
    items = Device.objects.filter(
        rx_signal__lte=-11,
        group__in=user_permitted_groups,
    )

    search_query = (request.GET.get('search') or '').strip()
    items = _apply_device_search(items, search_query)
    items = _build_enriched_device_queryset(items).order_by('rx_signal')

    paginator = Paginator(items, 100)
    page_items = paginator.get_page(request.GET.get('page'))
    return _render_filtered_device_list(
        request,
        template_name='devices_high_sig_11.html',
        page_items=page_items,
        title='Signal <= -11 dBm',
        subtitle='Attention required',
        search_query=search_query,
    )


@login_required
@permission_required('snmp.change_device', raise_exception=True)
@require_POST
def refresh_device_inventory(request, pk):
    from snmp.management.commands.snmp import perform_snmpwalk

    device = get_object_or_404(Device, pk=pk)
    if not user_can_access_device(request.user, device):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    hostname_resp = perform_snmpwalk(device.ip, OID_SYSTEM_HOSTNAME, SNMP_COMMUNITY)
    uptime_resp = perform_snmpwalk(device.ip, OID_SYSTEM_UPTIME, SNMP_COMMUNITY)
    if not hostname_resp or not uptime_resp:
        return JsonResponse({'error': 'Missing SNMP response'}, status=502)

    match_hostname = re.search(r'SNMPv2-MIB::sysName.0 = (.+)', hostname_resp[0])
    if not match_hostname:
        return JsonResponse({'error': 'Unexpected hostname response format.'}, status=500)
    device.hostname = match_hostname.group(1).strip()

    match_uptime = re.search(r'SNMPv2-MIB::sysUpTime.0\s*=\s*(\d+)', uptime_resp[0])
    if not match_uptime:
        return JsonResponse({'error': 'Unexpected uptime response format.'}, status=500)
    device.uptime = convert_uptime_to_human_readable(match_uptime.group(1).strip())

    description_resp = perform_snmpwalk(device.ip, OID_SYSTEM_DESCRIPTION, SNMP_COMMUNITY)
    if description_resp:
        response_description = str(description_resp[0]).strip().split()
        with transaction.atomic():
            if not device.device_type:
                model_instance = DeviceModel.objects.filter(device_model__in=response_description).first()
                if model_instance:
                    device.device_type = model_instance
            elif device.device_type.device_model not in response_description:
                model_instance = DeviceModel.objects.filter(device_model__in=response_description).first()
                if model_instance:
                    device.device_type = model_instance

    device.save()
    return redirect('device_detail', pk=pk)
