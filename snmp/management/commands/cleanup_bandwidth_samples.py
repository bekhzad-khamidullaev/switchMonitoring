import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from snmp.models import InterfaceBandwidthSample


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Delete InterfaceBandwidthSample rows older than retention period.'

    def add_arguments(self, parser):
        parser.add_argument('--retention-days', type=int, default=7)

    def handle(self, *args, **options):
        retention_days = int(options['retention_days'])
        cutoff = timezone.now() - timedelta(days=retention_days)
        deleted, _ = InterfaceBandwidthSample.objects.filter(ts__lt=cutoff).delete()
        logger.info('Deleted %s bandwidth samples older than %s days', deleted, retention_days)
