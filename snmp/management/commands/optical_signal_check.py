import time
from django.core.management.base import BaseCommand
from snmp.models import Olt

class Command(BaseCommand):
    help = 'Periodically check optical signal level'

    def handle(self, *args, **options):
        while True:
            olts = Olt.objects.all()
            for olt in olts:
                optical_signal = olt.get_optical_signal_status()  # Call your method to get the optical signal status
                # You can save the optical_signal value in a database or perform other actions

            time.sleep(60)  # Sleep for 60 seconds (adjust as needed)
