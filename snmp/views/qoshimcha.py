from snmp.models import Branch



def convert_uptime_to_human_readable(uptime_in_hundredths):
    total_seconds = int(uptime_in_hundredths) / 100.0
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    return f"{int(days)} days, {int(hours)} hours"


def get_permitted_branches(user):
    """Return queryset of branches the user is allowed to see."""
    qs = Branch.objects.all()

    if getattr(user, 'is_superuser', False):
        return qs

    permitted_ids = []
    for branch in qs:
        codename = f"snmp.view_{branch.name.lower().replace(' ', '_')}"
        if user.has_perm(codename):
            permitted_ids.append(branch.id)

    return Branch.objects.filter(id__in=permitted_ids)
