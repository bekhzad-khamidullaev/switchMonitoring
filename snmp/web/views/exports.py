import re
from datetime import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import CharField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from openpyxl import Workbook

from snmp.models import DevicePort, Mac

from .access import get_permitted_groups

_illegal_xml_chars_re = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
ENDPOINT_TYPE_RULES = {
    'printer': ('printer', 'hp ', 'xerox', 'canon', 'brother', 'epson', 'ricoh', 'kyocera', 'lexmark'),
    'voip': ('voip', 'phone', 'sip', 'yealink', 'grandstream', 'cisco ip phone', 'mitel'),
    'wifi': ('wifi', 'wlan', 'access point', 'ap-', 'ubiquiti', 'mikrotik', 'ruckus'),
    'camera': ('camera', 'cctv', 'ipcam', 'hikvision', 'dahua', 'axis'),
}


def sanitize_for_excel(text):
    if isinstance(text, str):
        return _illegal_xml_chars_re.sub('', text)
    return text


@login_required
def export_low_signal_devices_to_excel(request):
    current_datetime = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f'devices_low_signal_{current_datetime}.xlsx'

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Low Signal Devices'
    worksheet.append(['Group', 'Subgroup', 'Hostname', 'IP', 'Model', 'Port', 'Port name', 'Uptime', 'RX', 'TX', 'Last check'])

    permitted_groups = get_permitted_groups(request.user)
    items = (
        DevicePort.objects.filter(
            managed_device__group__in=permitted_groups,
            rx_signal__lte=-11,
        )
        .select_related('managed_device', 'managed_device__subgroup', 'managed_device__group', 'managed_device__device_type')
        .order_by('rx_signal', 'managed_device__hostname', 'port')
    )

    for item in items:
        device = item.managed_device
        group_name = sanitize_for_excel(device.group.name if device.group_id else '')
        subgroup_name = sanitize_for_excel(device.subgroup.name if device.subgroup_id else '')
        hostname = sanitize_for_excel(device.hostname)
        ip_address = sanitize_for_excel(device.ip)
        model_name = sanitize_for_excel(device.device_type.device_model if device.device_type else '')
        port_name = sanitize_for_excel(item.name or '')
        uptime_str = sanitize_for_excel(str(device.uptime or ''))
        last_update_str = device.updated.strftime('%Y-%m-%d %H:%M:%S') if device.updated else ''

        worksheet.append(
            [
                group_name,
                subgroup_name,
                hostname,
                ip_address,
                model_name,
                item.port,
                port_name,
                uptime_str,
                item.rx_signal,
                item.tx_signal,
                last_update_str,
            ]
        )

    workbook.save(response)
    return response


def _build_port_activity_queryset(permitted_groups):
    return (
        DevicePort.objects.filter(managed_device__group__in=permitted_groups)
        .select_related('managed_device', 'managed_device__group')
        .annotate(
            last_mac=Subquery(
                Mac.objects.filter(port=OuterRef('pk')).order_by('-data').values('mac')[:1]
            ),
            last_ip=Subquery(
                Mac.objects.filter(port=OuterRef('pk')).order_by('-data').values('ip')[:1]
            ),
            last_seen=Subquery(
                Mac.objects.filter(port=OuterRef('pk')).order_by('-data').values('data')[:1]
            ),
            searchable_alias=Coalesce('alias', Value('', output_field=CharField())),
            searchable_name=Coalesce('name', Value('', output_field=CharField())),
            searchable_desc=Coalesce('description', Value('', output_field=CharField())),
            searchable_host=Coalesce('managed_device__hostname', Value('', output_field=CharField())),
        )
        .order_by('managed_device__hostname', 'port')
    )


def _build_keyword_q(keywords):
    query = Q()
    for keyword in keywords:
        query |= Q(searchable_alias__icontains=keyword)
        query |= Q(searchable_name__icontains=keyword)
        query |= Q(searchable_desc__icontains=keyword)
        query |= Q(searchable_host__icontains=keyword)
    return query


def _apply_common_port_activity_search(queryset, search):
    if not search:
        return queryset
    return queryset.filter(
        Q(searchable_host__icontains=search)
        | Q(managed_device__ip__icontains=search)
        | Q(searchable_name__icontains=search)
        | Q(searchable_alias__icontains=search)
        | Q(searchable_desc__icontains=search)
        | Q(last_mac__icontains=search)
        | Q(last_ip__icontains=search)
    )


@login_required
@permission_required('snmp.view_device', raise_exception=True)
def port_activity_report(request):
    permitted_groups = get_permitted_groups(request.user)
    queryset = _build_port_activity_queryset(permitted_groups)

    search = (request.GET.get('search') or '').strip()
    queryset = _apply_common_port_activity_search(queryset, search)

    page_number = request.GET.get('page')
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(page_number)
    context = {
        'page_title': 'Port Activity Report',
        'page_subtitle': 'Latest MAC/IP observed on each port.',
        'report_url_name': 'port_activity_report',
        'page_obj': page_obj,
        'search': search,
    }
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'partials/port_activity_table.html', context)
    return render(request, 'port_activity_report.html', context)


@login_required
@permission_required('snmp.view_device', raise_exception=True)
def endpoint_activity_report(request, endpoint_type):
    endpoint_type = (endpoint_type or '').strip().lower()
    keywords = ENDPOINT_TYPE_RULES.get(endpoint_type)
    if keywords is None:
        return HttpResponse('Unknown endpoint type.', status=404)

    permitted_groups = get_permitted_groups(request.user)
    queryset = _build_port_activity_queryset(permitted_groups).filter(_build_keyword_q(keywords))

    search = (request.GET.get('search') or '').strip()
    queryset = _apply_common_port_activity_search(queryset, search)

    page_number = request.GET.get('page')
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(page_number)
    context = {
        'page_title': f'{endpoint_type.title()} Endpoint Report',
        'page_subtitle': 'Filtered by endpoint fingerprint keywords (hostname/name/alias/description).',
        'report_url_name': 'endpoint_activity_report',
        'endpoint_type': endpoint_type,
        'page_obj': page_obj,
        'search': search,
    }
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'partials/port_activity_table.html', context)
    return render(request, 'port_activity_report.html', context)
