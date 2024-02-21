from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Delete duplicate entries from the Switch model'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('''
                DELETE FROM snmp_switch
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM snmp_switch
                    GROUP BY hostname, ip
                );
            ''')

        self.stdout.write(self.style.SUCCESS('Duplicates deleted successfully.'))
