import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update optical info (deprecated: use update_optical_info_mib)'

    def handle(self, *args, **options):
        call_command('update_optical_info_mib')
        logger.info('Delegated to update_optical_info_mib')
