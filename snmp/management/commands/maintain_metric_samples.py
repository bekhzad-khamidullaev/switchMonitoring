from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from snmp.models import MetricSample


class Command(BaseCommand):
    help = "Delete old metric samples in bounded batches to keep table size predictable"

    def add_arguments(self, parser):
        parser.add_argument("--retention-days", type=int, default=30, dest="retention_days")
        parser.add_argument("--batch-size", type=int, default=20000, dest="batch_size")
        parser.add_argument("--max-batches", type=int, default=10, dest="max_batches")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")

    def handle(self, *args, **options):
        retention_days = max(1, int(options["retention_days"]))
        batch_size = max(1, int(options["batch_size"]))
        max_batches = max(1, int(options["max_batches"]))
        dry_run = bool(options["dry_run"])

        cutoff = timezone.now() - timedelta(days=retention_days)
        base_qs = MetricSample.objects.filter(ts__lt=cutoff)
        total_candidates = base_qs.count()

        deleted = 0
        batches = 0
        while batches < max_batches:
            ids = list(
                base_qs.order_by("id").values_list("id", flat=True)[:batch_size]
            )
            if not ids:
                break

            batches += 1
            if dry_run:
                deleted += len(ids)
                continue

            deleted += MetricSample.objects.filter(id__in=ids).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"metric_sample_maintenance cutoff={cutoff.isoformat()} "
                f"candidates={total_candidates} batches={batches} "
                f"{'would_delete' if dry_run else 'deleted'}={deleted}"
            )
        )
