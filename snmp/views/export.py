import re
from django.http import HttpResponse
from openpyxl import Workbook
from snmp.models import Switch
from .qoshimcha import get_permitted_branches
from datetime import datetime

def sanitize_excel_string(value):
    """Remove invalid characters from strings to prevent Excel errors."""
    if value:
        return re.sub(r'[\x00-\x1F\x7F]', '', value)  # Remove control characters
    return ''

def export_high_sig_switches_to_excel(request):
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"switches_with_high_sig_lvl_{current_datetime}.xlsx"

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(['Branch', 'ATS', 'Hostname', 'IP', 'Model', 'Uptime', 'RX', 'TX', 'Last check'])

    user_permitted_branches = get_permitted_branches(request.user)
    switches = Switch.objects.filter(
        rx_signal__lte=-11, branch__in=user_permitted_branches
    ).order_by('rx_signal')

    for switch in switches:
        worksheet.append([
            sanitize_excel_string(switch.ats.branch.name),
            sanitize_excel_string(switch.ats.name),
            sanitize_excel_string(switch.hostname),
            sanitize_excel_string(switch.ip),
            sanitize_excel_string(switch.model.device_model) if switch.model else '',
            sanitize_excel_string(switch.uptime) or '',
            switch.rx_signal,
            switch.tx_signal,
            switch.last_update.strftime('%Y-%m-%d %H:%M:%S') if switch.last_update else '',
        ])

    workbook.save(response)
    return response
