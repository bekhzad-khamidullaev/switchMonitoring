from snmp.models import Branch


def build_branch_permission_codename(branch_name):
    if not branch_name:
        return None
    return f"view_{branch_name.lower().replace(' ', '_')}"


def user_has_global_device_access(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return (
        user.has_perm("snmp.view_switch")
        or user.has_perm("snmp.change_switch")
        or user.has_perm("snmp.view_device")
        or user.has_perm("snmp.change_device")
    )


def user_can_access_managed_device(user, managed_device):
    if not user or not user.is_authenticated:
        return False
    if user_has_global_device_access(user):
        return True
    if managed_device.branch_id is None:
        return False
    permitted_ids = {branch.id for branch in get_permitted_branches(user)}
    return managed_device.branch_id in permitted_ids


def convert_uptime_to_human_readable(uptime_in_hundredths):
    total_seconds = int(uptime_in_hundredths) / 100.0
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    return f"{int(days)} days, {int(hours)} hours"


def get_permitted_branches(user):
    branches = Branch.objects.all()
    permitted_branches = []
    for branch in branches:
        codename = build_branch_permission_codename(branch.name)
        if codename and user.has_perm(f"snmp.{codename}"):
            permitted_branches.append(branch)
    return permitted_branches
