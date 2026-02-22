from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from snmp.models import Device, DeviceProfile, MetricBinding, MetricDefinition, MetricSubscription
from snmp.services.metrics.interface_filters import is_eligible_optical_ethernet, is_gpon

ICMP_BINDING_SENTINEL = "__icmp_ping__"
PORT_RX_SIGNAL_SENTINEL = "__port_rx_signal__"
PORT_TX_SIGNAL_SENTINEL = "__port_tx_signal__"


class Command(BaseCommand):
    help = (
        "Ensure baseline monitoring on all devices: sys_uptime, sys_hostname, sys_info, icmp_ping_ms, "
        "plus optical_rx_power/optical_tx_power on Ethernet optical interfaces (excluding GPON)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Do not persist any changes")
        parser.add_argument("--limit", type=int, default=0, help="Limit number of devices processed")
        parser.add_argument("--poll-interval", type=int, default=300, help="Default poll interval for created subscriptions")

    def _get_or_create_baseline_bindings(self, poll_interval: int):
        profile, _ = DeviceProfile.objects.get_or_create(
            vendor="generic",
            model_pattern="BASELINE_MONITORING",
            firmware_pattern="",
            defaults={"priority": 1, "active": True},
        )
        if not profile.active:
            profile.active = True
            profile.save(update_fields=["active"])

        definitions = {
            "sys_uptime": {
                "title": "System Uptime",
                "description": "SNMP sysUpTime.0",
                "unit": "ticks",
                "value_type": MetricDefinition.ValueType.INTEGER,
            },
            "sys_hostname": {
                "title": "System Hostname",
                "description": "SNMP sysName.0",
                "unit": "",
                "value_type": MetricDefinition.ValueType.TEXT,
            },
            "sys_info": {
                "title": "System Description",
                "description": "SNMP sysDescr.0",
                "unit": "",
                "value_type": MetricDefinition.ValueType.TEXT,
            },
            "icmp_ping_ms": {
                "title": "ICMP Ping Latency",
                "description": "ICMP round-trip time",
                "unit": "ms",
                "value_type": MetricDefinition.ValueType.FLOAT,
            },
            "optical_rx_power": {
                "title": "Optical RX Power",
                "description": "Optical receiver power level",
                "unit": "dBm",
                "value_type": MetricDefinition.ValueType.FLOAT,
            },
            "optical_tx_power": {
                "title": "Optical TX Power",
                "description": "Optical transmitter power level",
                "unit": "dBm",
                "value_type": MetricDefinition.ValueType.FLOAT,
            },
        }
        oids = {
            "sys_uptime": "1.3.6.1.2.1.1.3.0",
            "sys_hostname": "1.3.6.1.2.1.1.5.0",
            "sys_info": "1.3.6.1.2.1.1.1.0",
            "icmp_ping_ms": ICMP_BINDING_SENTINEL,
            "optical_rx_power": PORT_RX_SIGNAL_SENTINEL,
            "optical_tx_power": PORT_TX_SIGNAL_SENTINEL,
        }

        bindings = {}
        for key, meta in definitions.items():
            metric, _ = MetricDefinition.objects.get_or_create(
                key=key,
                defaults={
                    "title": meta["title"],
                    "description": meta["description"],
                    "unit": meta["unit"],
                    "value_type": meta["value_type"],
                    "default_interval_sec": poll_interval,
                },
            )
            updates = []
            if metric.default_interval_sec != poll_interval:
                metric.default_interval_sec = poll_interval
                updates.append("default_interval_sec")
            if updates:
                metric.save(update_fields=updates)

            index_strategy = (
                MetricBinding.IndexStrategy.IF_INDEX
                if key in {"optical_rx_power", "optical_tx_power"}
                else MetricBinding.IndexStrategy.FIXED
            )
            default_binding_params = {"fixed_index": 0} if index_strategy == MetricBinding.IndexStrategy.FIXED else {}

            binding, _ = MetricBinding.objects.get_or_create(
                profile=profile,
                metric=metric,
                oid_template=oids[key],
                index_strategy=index_strategy,
                defaults={
                    "converter": MetricBinding.Converter.IDENTITY,
                    "enabled_by_default": True,
                    "priority": 10,
                    "binding_params": default_binding_params,
                },
            )
            binding_updates = []
            binding_params = dict(binding.binding_params or {})
            if index_strategy == MetricBinding.IndexStrategy.FIXED and binding_params.get("fixed_index") is None:
                binding_params["fixed_index"] = 0
                binding.binding_params = binding_params
                binding_updates.append("binding_params")
            if binding_updates:
                binding.save(update_fields=binding_updates)
            bindings[key] = binding

        return bindings

    @staticmethod
    def _upsert_subscription(
        *,
        device: Device,
        metric: MetricDefinition,
        binding: MetricBinding,
        interface: Interface | None,
        poll_interval: int,
        dry_run: bool,
    ) -> bool:
        if interface is None:
            subscription = MetricSubscription.objects.filter(
                device=device,
                interface__isnull=True,
                metric=metric,
            ).first()
        else:
            subscription = MetricSubscription.objects.filter(
                device=device,
                interface=interface,
                metric=metric,
            ).first()

        created = subscription is None
        if created:
            if not dry_run:
                MetricSubscription.objects.create(
                    device=device,
                    interface=interface,
                    metric=metric,
                    binding=binding,
                    enabled=True,
                    poll_interval_sec=poll_interval,
                )
            return True

        changed = False
        if subscription.binding_id != binding.id:
            subscription.binding = binding
            changed = True
        if not subscription.enabled:
            subscription.enabled = True
            changed = True
        if subscription.poll_interval_sec is None:
            subscription.poll_interval_sec = poll_interval
            changed = True
        if changed and not dry_run:
            subscription.save(update_fields=["binding", "enabled", "poll_interval_sec"])
        return changed

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        limit = int(options["limit"] or 0)
        poll_interval = max(5, int(options["poll_interval"] or 300))

        baseline_bindings = self._get_or_create_baseline_bindings(poll_interval=poll_interval)
        devices_qs = Device.objects.all().order_by("id")
        if limit > 0:
            devices_qs = devices_qs[:limit]
        devices = list(devices_qs)

        self.stdout.write(f"Processing devices: {len(devices)} (dry_run={dry_run})")

        stats = {
            "baseline_subscriptions_changed": 0,
            "optical_subscriptions_changed": 0,
            "interfaces_eligible": 0,
            "interfaces_skipped_gpon": 0,
        }

        with transaction.atomic():
            for device in devices:
                for key in ("sys_uptime", "sys_hostname", "sys_info", "icmp_ping_ms"):
                    binding = baseline_bindings[key]
                    if self._upsert_subscription(
                        device=device,
                        metric=binding.metric,
                        binding=binding,
                        interface=None,
                        poll_interval=poll_interval,
                        dry_run=dry_run,
                    ):
                        stats["baseline_subscriptions_changed"] += 1

                profile = device.profile
                if not profile:
                    continue

                optical_bindings = list(
                    MetricBinding.objects.filter(
                        profile=profile,
                        metric__key__in=("optical_rx_power", "optical_tx_power"),
                        index_strategy=MetricBinding.IndexStrategy.IF_INDEX,
                    ).select_related("metric")
                )
                if not optical_bindings:
                    optical_bindings = [
                        baseline_bindings["optical_rx_power"],
                        baseline_bindings["optical_tx_power"],
                    ]

                for interface in device.interfaces.all():
                    if is_gpon(interface):
                        stats["interfaces_skipped_gpon"] += 1
                        continue
                    if not is_eligible_optical_ethernet(interface):
                        continue
                    stats["interfaces_eligible"] += 1
                    for binding in optical_bindings:
                        if self._upsert_subscription(
                            device=device,
                            metric=binding.metric,
                            binding=binding,
                            interface=interface,
                            poll_interval=poll_interval,
                            dry_run=dry_run,
                        ):
                            stats["optical_subscriptions_changed"] += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "Done. "
                f"baseline_changed={stats['baseline_subscriptions_changed']} "
                f"optical_changed={stats['optical_subscriptions_changed']} "
                f"eligible_ifaces={stats['interfaces_eligible']} "
                f"skipped_gpon={stats['interfaces_skipped_gpon']}"
            )
        )
