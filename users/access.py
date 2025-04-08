from snmp.models import Switch
from users.models import AccessPermission

def get_user_switch_queryset(user):
    if user.is_superuser:
        return Switch.objects.all()

    permissions = AccessPermission.objects.filter(user=user)
    allowed_switches = Switch.objects.none()

    for perm in permissions:
        if perm.node:
            allowed_switches |= Switch.objects.filter(ats__node=perm.node)
        elif perm.ats:
            allowed_switches |= Switch.objects.filter(ats=perm.ats)

    return allowed_switches.distinct()
