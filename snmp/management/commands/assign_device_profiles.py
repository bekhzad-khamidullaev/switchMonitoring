from django.core.management.base import BaseCommand

from snmp.models import Device
from snmp.services.discovery.normalize import normalize_vendor_model
from snmp.services.discovery.profile_matcher import match_device_profile


class Command(BaseCommand):
    help = 'Assign DeviceProfiles to Devices based on vendor, model, and firmware'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do not save changes')
        parser.add_argument('--force', action='store_true', help='Re-assign even if device already has a profile')
        parser.add_argument('--limit', type=int, help='Limit the number of devices to process')
        parser.add_argument('--verbose', action='store_true', help='Show detailed matching info')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        limit = options['limit']
        verbose = options['verbose']

        devices = Device.objects.all()
        if not force:
            devices = devices.filter(profile__isnull=True)

        if limit:
            devices = devices[:limit]

        total_count = devices.count()
        self.stdout.write(f"Processing {total_count} devices...")

        assigned = 0
        failed = 0
        skipped = 0

        for device in devices:
            vendor = device.vendor
            model = device.model
            firmware = device.firmware or ""

            # If metadata is incomplete, at least derive vendor from sysObjectID.
            if not vendor and device.sys_object_id:
                normalized = normalize_vendor_model(device.sys_object_id, "")
                detected_vendor = normalized.get("vendor", "")
                if detected_vendor and detected_vendor != "unknown":
                    vendor = detected_vendor

            if not vendor and device.device_type and device.device_type.vendor:
                vendor = device.device_type.vendor.name
            if not model and device.device_type:
                model = device.device_type.device_model

            profile = match_device_profile(
                vendor=vendor,
                model=model,
                firmware=firmware
            )

            if profile:
                if verbose:
                    self.stdout.write(
                        f"Metadata match for {device.ip} ({vendor or 'unknown'}/{model or 'unknown'}): {profile}"
                    )

                if not dry_run:
                    device.profile = profile
                    device.save()
                assigned += 1
            else:
                if verbose:
                    self.stdout.write(self.style.WARNING(f"No profile match for {device.ip} ({vendor}/{model}/{firmware})"))
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Finished. Assigned: {assigned}, No match: {failed}, Skipped (no info): {skipped}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes were committed to the database."))
