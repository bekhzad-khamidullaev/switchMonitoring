import re # Import the regular expression module
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Min
from openpyxl import Workbook

from snmp.models import Switch, Interface, InterfaceOptics

# Assuming get_permitted_branches is correctly imported from .qoshimcha
from .qoshimcha import get_permitted_branches

# --- Sanitization Function ---
# Regex to match illegal XML characters (control characters 0x00-0x1F, excluding \t, \n, \r)
# \x00-\x08, \x0b, \x0c, \x0e-\x1f
_illegal_xml_chars_re = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

def sanitize_for_excel(text):
    """Removes illegal XML characters from a string."""
    if isinstance(text, str):
        return _illegal_xml_chars_re.sub('', text) # Replace illegal chars with empty string
    return text # Return non-string types (like numbers, None) as is
# --- End Sanitization Function ---

@login_required
def export_high_sig_switches_to_excel(request):
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"switches_with_high_sig_lvl_{current_datetime}.xlsx"

    # Use the more specific content type for .xlsx files
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "High Signal Switches" # Optional: Give the sheet a name
    worksheet.append(['Branch', 'ATS', 'Hostname', 'IP', 'Model', 'Uptime', 'RX', 'TX', 'Last check'])

    user_permitted_branches = get_permitted_branches(request.user)
    switches = (
        Switch.objects
        .filter(ats__branch__in=user_permitted_branches)
        .annotate(min_rx=Min('interfaces__optics__rx_dbm'), min_tx=Min('interfaces__optics__tx_dbm'))
        .filter(min_rx__lte=-11)
        .select_related('ats', 'ats__branch', 'model')
        .order_by('min_rx')
    )
    for switch in switches:
        # *** Sanitize string fields before appending ***
        branch_name = sanitize_for_excel(switch.ats.branch.name)
        ats_name = sanitize_for_excel(switch.ats.name)
        hostname = sanitize_for_excel(switch.hostname)
        ip_address = sanitize_for_excel(switch.ip)
        model_name = sanitize_for_excel(switch.model.device_model if switch.model else '')
        # Ensure uptime is treated as a string before sanitizing if it might be complex
        uptime_str = sanitize_for_excel(str(switch.uptime or ''))
        last_update_str = switch.last_update.strftime('%Y-%m-%d %H:%M:%S') if switch.last_update else ''
        # rx/tx signals are likely numeric, no sanitization needed unless they are stored as strings

        worksheet.append([
            branch_name,
            ats_name,
            hostname,
            ip_address,
            model_name,
            uptime_str,
            switch.min_rx, # Numeric
            switch.min_tx, # Numeric
            last_update_str,  # Already formatted string, usually safe
        ])

    workbook.save(response)
    return response


@login_required
def export_optical_ports_to_excel(request):
    """Export optical ports report from SwitchesPorts (per-port optics).

    Query params:
      - min_rx: include ports with rx_signal <= min_rx
      - max_rx: include ports with rx_signal >= max_rx
      - only_optical=1: require both rx_signal and tx_signal to be present
    """
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"optical_ports_{current_datetime}.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Optical Ports"

    worksheet.append([
        'Branch', 'ATS', 'Hostname', 'IP', 'Model',
        'ifIndex', 'ifName', 'ifAlias', 'ifDescr',
        'Speed', 'Admin', 'Oper',
        'RX(dBm)', 'TX(dBm)',
        'SFP Vendor', 'Part Number', 'Serial Number',
        'Last Poll',
    ])

    user_permitted_branches = get_permitted_branches(request.user)
    qs = (
        Interface.objects
        .select_related('switch', 'switch__ats', 'switch__ats__branch', 'switch__model')
        .filter(switch__ats__branch__in=user_permitted_branches)
    )

    # Optional filters
    min_rx = request.GET.get('min_rx')
    if min_rx not in (None, ''):
        try:
            qs = qs.filter(optics__rx_dbm__lte=float(min_rx))
        except ValueError:
            pass

    max_rx = request.GET.get('max_rx')
    if max_rx not in (None, ''):
        try:
            qs = qs.filter(optics__rx_dbm__gte=float(max_rx))
        except ValueError:
            pass

    only_optical = request.GET.get('only_optical')
    if str(only_optical) in ('1', 'true', 'True', 'yes', 'on'):
        qs = qs.exclude(optics__rx_dbm__isnull=True).exclude(optics__tx_dbm__isnull=True)

    qs = qs.order_by('switch__ats__branch__name', 'switch__ats__name', 'switch__hostname', 'ifindex')

    for p in qs:
        sw = p.switch
        optics = getattr(p, 'optics', None)
        ats = getattr(sw, 'ats', None)
        branch = getattr(ats, 'branch', None) if ats else None

        worksheet.append([
            sanitize_for_excel(getattr(branch, 'name', '') or ''),
            sanitize_for_excel(getattr(ats, 'name', '') or ''),
            sanitize_for_excel(sw.hostname or ''),
            sanitize_for_excel(str(sw.ip or '')),
            sanitize_for_excel(sw.model.device_model if sw.model else ''),
            p.ifindex,
            sanitize_for_excel(p.name or ''),
            sanitize_for_excel(p.alias or ''),
            sanitize_for_excel(p.description or ''),
            p.speed,
            p.admin,
            p.oper,
            getattr(optics, 'rx_dbm', None),
            getattr(optics, 'tx_dbm', None),
            sanitize_for_excel(getattr(optics, 'sfp_vendor', '') or ''),
            sanitize_for_excel(getattr(optics, 'part_number', '') or ''),
            sanitize_for_excel(getattr(optics, 'serial_number', '') or ''),
            (getattr(optics, 'polled_at', None) or p.polled_at).strftime('%Y-%m-%d %H:%M:%S') if (getattr(optics, 'polled_at', None) or p.polled_at) else '',
        ])

    workbook.save(response)
    return response