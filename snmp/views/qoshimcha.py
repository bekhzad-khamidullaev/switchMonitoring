from snmp.models import Branch



def convert_uptime_to_human_readable(uptime_in_hundredths):
    total_seconds = int(uptime_in_hundredths) / 100.0
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    return f"{int(days)} days, {int(hours)} hours"


def get_permitted_branches(user):
    branches = Branch.objects.all()
    permitted_branches = []
    for branch in branches:
        if user.has_perm(f'snmp.view_{branch.name.lower().replace(" ", "_")}'):
            permitted_branches.append(branch)      
    return permitted_branches