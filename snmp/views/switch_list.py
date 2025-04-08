from django.shortcuts import render
from snmp.models import Switch
from users.access import get_user_switch_queryset
from django.contrib.auth.decorators import login_required

@login_required
def switch_list(request):
    switches = get_user_switch_queryset(request.user).select_related('ats', 'ats__node')
    return render(request, 'snmp/switch_list.html', {'switches': switches})
