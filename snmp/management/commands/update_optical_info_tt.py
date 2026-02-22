from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Deprecated: delegates to update_optical_info (multi-port optical ethernet, excludes GPON).'

    def add_arguments(self, parser):
        parser.add_argument('--community', required=False, help='Accepted for compatibility, ignored.')
        parser.add_argument('--continuous', action='store_true', help='Accepted for compatibility, ignored.')

    def handle(self, *args, **options):
        call_command('update_optical_info')
