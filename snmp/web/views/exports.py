import re
from datetime import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponse
from django.shortcuts import render
from openpyxl import Workbook

from snmp.models import Device as DeviceModel
from snmp.models import DevicePort, Mac

from .access import get_permitted_branches

_illegal_xml_chars_re = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


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
    worksheet.append(['Branch', 'ATS', 'Hostname', 'IP', 'Model', 'Uptime', 'RX', 'TX', 'Last check'])

    permitted_branches = get_permitted_branches(request.user)
    items = (
        DeviceModel.objects.filter(rx_signal__lte=-11, branch__in=permitted_branches)
        .select_related('ats', 'ats__branch', 'device_type')
        .order_by('rx_signal')
    )

    for item in items:
        branch_name = sanitize_for_excel(item.branch.name if item.branch_id else '')
        ats_name = sanitize_for_excel(item.ats.name if item.ats_id else '')
        hostname = sanitize_for_excel(item.hostname)
        ip_address = sanitize_for_excel(item.ip)
        model_name = sanitize_for_excel(item.device_type.device_model if item.device_type else '')
        uptime_str = sanitize_for_excel(str(item.uptime or ''))
        last_update_str = item.last_update.strftime('%Y-%m-%d %H:%M:%S') if item.last_update else ''

        worksheet.append(
            [
                branch_name,
                ats_name,
                hostname,
                ip_address,
                model_name,
                uptime_str,
                item.rx_signal,
                item.tx_signal,
                last_update_str,
            ]
        )

    workbook.save(response)
    return response


@login_required
@permission_required('snmp.view_device', raise_exception=True)
def port_activity_report(request):
    permitted_branches = get_permitted_branches(request.user)
    queryset = (
        DevicePort.objects.filter(managed_device__branch__in=permitted_branches)
        .select_related('managed_device', 'managed_device__branch')
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
        )
        .order_by('managed_device__hostname', 'port')
    )

    search = (request.GET.get('search') or '').strip()
    if search:
        queryset = queryset.filter(
            Q(managed_device__hostname__icontains=search)
            | Q(managed_device__ip__icontains=search)
            | Q(name__icontains=search)
            | Q(alias__icontains=search)
            | Q(description__icontains=search)
            | Q(last_mac__icontains=search)
            | Q(last_ip__icontains=search)
        )

    page_number = request.GET.get('page')
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        'port_activity_report.html',
        {
            'page_obj': page_obj,
            'search': search,
        },
    )
