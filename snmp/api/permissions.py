from snmp.models import Device
from snmp.web.views.access import get_permitted_branches


def user_can_access_device(user, device: Device) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    if device.branch_id is None:
        return user.has_perm('snmp.change_device') or user.has_perm('snmp.view_device')

    permitted = {b.id for b in get_permitted_branches(user)}
    return device.branch_id in permitted
