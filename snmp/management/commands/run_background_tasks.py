from django.core.management.base import BaseCommand
from snmp.management.commands.update_switch_inventory import update_switch_inventory_main
from snmp.management.commands.update_switch_status import update_switch_status_main
from background_task.models import Task

class Command(BaseCommand):
    help = 'Run background tasks'

    def handle(self, *args, **options):
        update_switch_inventory_main()
        update_switch_status_main()
