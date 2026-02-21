from snmp.models import Device
from snmp.web.views.access import get_permitted_groups


def user_can_access_device(user, device: Device) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    if device.group_id is None:
        return user.has_perm('snmp.change_device') or user.has_perm('snmp.view_device')

    permitted = {g.id for g in get_permitted_groups(user)}
    return device.group_id in permitted


def user_can_create_device(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.has_perm('snmp.add_device')


def user_can_manage_device(user, device: Device) -> bool:
    if not user_can_access_device(user, device):
        return False
    return user.is_superuser or user.has_perm('snmp.change_device')
