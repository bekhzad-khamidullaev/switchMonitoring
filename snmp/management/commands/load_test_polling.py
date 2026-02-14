import time
import uuid
from contextlib import contextmanager

from django.core.management.base import BaseCommand
from django.db import transaction

from snmp.models import Device, DeviceProfile, Interface, MetricBinding, MetricDefinition, MetricSubscription
from snmp.services.polling.poller import poll_device_metrics


@contextmanager
def fake_snmp_get_many(enabled: bool):
    if not enabled:
        yield
        return

    from snmp.services.polling import poller as poller_module

    original = poller_module.snmp_get_many

    def _fake_get_many(ip, community, oids, timeout=2, retries=1, batch_size=20):
        return {oid: "-1234" for oid in oids}

    poller_module.snmp_get_many = _fake_get_many
    try:
        yield
    finally:
        poller_module.snmp_get_many = original


class Command(BaseCommand):
    help = "Load test for polling engine on synthetic devices in test environment."

    def add_arguments(self, parser):
        parser.add_argument("--devices", type=int, default=20)
        parser.add_argument("--interfaces", type=int, default=8)
        parser.add_argument("--metrics-per-interface", type=int, default=2)
        parser.add_argument("--fake-snmp", action="store_true", default=False)
        parser.add_argument("--cleanup", action="store_true", default=False)

    def handle(self, *args, **options):
        devices_count = max(1, options["devices"])
        interfaces_count = max(1, options["interfaces"])
        metrics_per_interface = max(1, options["metrics_per_interface"])
        fake_snmp = options["fake_snmp"]
        cleanup = options["cleanup"]
        batch_id = uuid.uuid4().hex[:8]
        second_octet = (int(batch_id[:2], 16) % 200) + 1

        metric_keys = [f"lt_{batch_id}_metric_{i}" for i in range(metrics_per_interface)]
        profile = DeviceProfile.objects.create(
            vendor=f"loadtest-{batch_id}",
            model_pattern=r"LT-\d+",
            firmware_pattern="",
            priority=1,
            active=True,
        )

        metrics = []
        bindings = []
        for metric_key in metric_keys:
            metric = MetricDefinition.objects.create(
                key=metric_key,
                title=f"Load test {metric_key}",
                unit="dBm",
                value_type=MetricDefinition.ValueType.FLOAT,
                default_interval_sec=60,
            )
            binding = MetricBinding.objects.create(
                profile=profile,
                metric=metric,
                oid_template=f"1.3.6.1.4.1.55555.1.{len(metrics) + 1}.{{if_index}}",
                index_strategy=MetricBinding.IndexStrategy.IF_INDEX,
                converter=MetricBinding.Converter.DIV100,
                enabled_by_default=True,
                priority=1,
            )
            metrics.append(metric)
            bindings.append(binding)

        device_ids = []
        with transaction.atomic():
            for i in range(devices_count):
                host_octet = (i % 250) + 1
                subnet_octet = (i // 250) + 1
                ip = f"10.{second_octet}.{subnet_octet}.{host_octet}"
                device = Device.objects.create(
                    ip=ip,
                    hostname=f"lt-{batch_id}-{i}",
                    vendor=profile.vendor,
                    model="LT-1000",
                    profile=profile,
                    status=True,
                )
                device_ids.append(device.id)

                interfaces = []
                for if_index in range(1, interfaces_count + 1):
                    interfaces.append(
                        Interface(
                            device=device,
                            if_index=if_index,
                            if_name=f"eth{if_index}",
                            if_alias=f"loadtest-{if_index}",
                            if_type="117",
                            is_optical=True,
                            admin_up=True,
                            oper_up=True,
                        )
                    )
                Interface.objects.bulk_create(interfaces, batch_size=1000)

                created_interfaces = list(Interface.objects.filter(device=device))
                subscriptions = []
                for iface in created_interfaces:
                    for metric, binding in zip(metrics, bindings):
                        subscriptions.append(
                            MetricSubscription(
                                device=device,
                                interface=iface,
                                metric=metric,
                                binding=binding,
                                enabled=True,
                                poll_interval_sec=60,
                            )
                        )
                MetricSubscription.objects.bulk_create(subscriptions, batch_size=2000)

        started = time.monotonic()
        total_samples = 0
        with fake_snmp_get_many(fake_snmp):
            for device_id in device_ids:
                total_samples += poll_device_metrics(device_id)
        elapsed = time.monotonic() - started

        self.stdout.write(
            self.style.SUCCESS(
                "load_test_report "
                f"devices={devices_count} interfaces={interfaces_count} metrics_per_interface={metrics_per_interface} "
                f"total_samples={total_samples} elapsed_sec={elapsed:.2f} samples_per_sec={total_samples / elapsed:.2f}"
            )
        )

        if cleanup:
            Device.objects.filter(id__in=device_ids).delete()
            MetricDefinition.objects.filter(key__in=metric_keys).delete()
            DeviceProfile.objects.filter(id=profile.id).delete()
            self.stdout.write(self.style.WARNING("load_test_cleanup completed"))
