from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_branch_permissions(sender, **kwargs):
    """Create per-branch permissions after snmp migrations.

    Kept defensive to avoid breaking global migrate/app loading.
    """
    if getattr(sender, 'name', None) != 'snmp':
        return

    # Local import to ensure apps are loaded
    from snmp.models import Branch

    try:
        content_type = ContentType.objects.get_for_model(Branch)
    except Exception:
        return

    for branch in Branch.objects.all():
        if not branch.name:
            continue
        codename = f"view_{branch.name.lower().replace(' ', '_')}"
        name = f"Can view switches in {branch.name}"
        try:
            Permission.objects.get_or_create(
                codename=codename,
                name=name,
                content_type=content_type,
            )
        except Exception:
            continue
