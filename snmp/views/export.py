import re # Import the regular expression module
from django.http import HttpResponse
from openpyxl import Workbook
from snmp.models import Switch
# Assuming get_permitted_branches is correctly imported from .qoshimcha
from .qoshimcha import get_permitted_branches
from datetime import datetime

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
    switches = Switch.objects.filter(
        rx_signal__lte=-11, branch__in=user_permitted_branches
    ).select_related('ats', 'ats__branch', 'model').order_by('rx_signal') # Use select_related for efficiency

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
            switch.rx_signal, # Numeric
            switch.tx_signal, # Numeric
            last_update_str,  # Already formatted string, usually safe
        ])

    workbook.save(response)
    return response