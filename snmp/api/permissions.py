from snmp.models import Device
from snmp.views.qoshimcha import get_permitted_branches


def user_can_access_device(user, device: Device) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    if not device.switch_id:
        return user.has_perm('snmp.change_device') or user.has_perm('snmp.view_device')

    switch = device.switch
    if switch.branch_id is None:
        return user.has_perm('snmp.change_device') or user.has_perm('snmp.view_device')

    permitted = {b.id for b in get_permitted_branches(user)}
    return switch.branch_id in permitted
