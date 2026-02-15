import re
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from openpyxl import Workbook

from snmp.models import ManagedDevice as ManagedDeviceModel

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
        ManagedDeviceModel.objects.filter(rx_signal__lte=-11, branch__in=permitted_branches)
        .select_related('ats', 'ats__branch', 'model')
        .order_by('rx_signal')
    )

    for item in items:
        branch_name = sanitize_for_excel(item.branch.name if item.branch_id else '')
        ats_name = sanitize_for_excel(item.ats.name if item.ats_id else '')
        hostname = sanitize_for_excel(item.hostname)
        ip_address = sanitize_for_excel(item.ip)
        model_name = sanitize_for_excel(item.model.device_model if item.model else '')
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
