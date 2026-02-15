from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from snmp.models import DeviceProfile, MetricBinding
import re

class Command(BaseCommand):
    help = 'Consolidate multiple device profiles per vendor into a single unified profile'

    def handle(self, *args, **options):
        # 1. Standardize vendor names to lowercase
        profiles = DeviceProfile.objects.all()
        for p in profiles:
            if p.vendor != p.vendor.lower():
                p.vendor = p.vendor.lower()
                p.save(update_fields=['vendor'])

        # 2. Get unique vendors
        vendors = DeviceProfile.objects.values_list('vendor', flat=True).distinct()
        
        total_merged = 0
        total_deleted = 0

        for vendor in vendors:
            vendor_profiles = (
                DeviceProfile.objects.filter(vendor=vendor)
                .annotate(b_count=Count('metric_bindings'))
                .order_by('-b_count', 'id')
            )
            
            if vendor_profiles.count() <= 1:
                continue

            # Pick the master (one with the most bindings)
            master = vendor_profiles[0]
            secondaries = vendor_profiles[1:]

            self.stdout.write(f"Consolidating vendor: {vendor} ({len(vendor_profiles)} profiles)")

            combined_patterns = set(p.model_pattern for p in vendor_profiles)
            # Remove redundant patterns (e.g. if one is '.*')
            if '.*' in combined_patterns:
                master.model_pattern = '.*'
            else:
                master.model_pattern = '|'.join(sorted(list(combined_patterns)))
            
            # Limit pattern length
            if len(master.model_pattern) > 250:
                master.model_pattern = '.*'
            
            master.save(update_fields=['model_pattern'])

            with transaction.atomic():
                # Safety check: ensure OIDs for the same metric don't conflict across profiles
                metric_to_oids = {}
                for p in vendor_profiles:
                    for b in p.metric_bindings.all():
                        if b.metric_id not in metric_to_oids:
                            metric_to_oids[b.metric_id] = set()
                        metric_to_oids[b.metric_id].add(b.oid_template)
                
                conflicting_metrics = [m_id for m_id, oids in metric_to_oids.items() if len(oids) > 1]
                if conflicting_metrics:
                    self.stdout.write(self.style.WARNING(f"Skipping vendor {vendor}: OID conflicts found for metrics {conflicting_metrics}"))
                    continue

                for secondary in secondaries:
                    # Move bindings
                    bindings = secondary.metric_bindings.all()
                    for binding in bindings:
                        # Check if master already has a binding for this metric/oid/strategy
                        exists = MetricBinding.objects.filter(
                            profile=master,
                            metric=binding.metric,
                            oid_template=binding.oid_template,
                            index_strategy=binding.index_strategy
                        ).exists()
                        
                        if not exists:
                            binding.profile = master
                            binding.save(update_fields=['profile'])
                        else:
                            # Already exists, just delete the secondary's binding
                            binding.delete()
                    
                    # Delete the secondary profile
                    secondary.delete()
                    total_deleted += 1
            
            total_merged += 1

        self.stdout.write(self.style.SUCCESS(f"Consolidation complete. Merged {total_merged} vendors, deleted {total_deleted} redundant profiles."))
