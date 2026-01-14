from django.core.management.base import BaseCommand

from snmp.models import Branch, HostGroup


class Command(BaseCommand):
    help = 'Create one root HostGroup per Branch (Region) if missing.'

    def handle(self, *args, **options):
        created = 0
        for b in Branch.objects.all():
            root_name = 'Root'
            obj, was_created = HostGroup.objects.get_or_create(
                branch=b,
                parent=None,
                name=root_name,
                defaults={'sort_order': 0},
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'Created {created} root groups.'))
