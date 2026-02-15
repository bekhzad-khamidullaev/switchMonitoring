from snmp.models import Device, ManagedDevice
from snmp.web.views.access import get_permitted_branches


def user_can_access_device(user, device: Device) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    if not device.managed_device_id:
        return user.has_perm('snmp.change_device') or user.has_perm('snmp.view_device')

    managed_device = device.managed_device
    if managed_device.branch_id is None:
        return user.has_perm('snmp.change_device') or user.has_perm('snmp.view_device')

    permitted = {b.id for b in get_permitted_branches(user)}
    return managed_device.branch_id in permitted


def user_can_access_managed_device(user, managed_device: ManagedDevice) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if managed_device.branch_id is None:
        return user.has_perm('snmp.change_device') or user.has_perm('snmp.view_device')
    permitted = {b.id for b in get_permitted_branches(user)}
    return managed_device.branch_id in permitted
