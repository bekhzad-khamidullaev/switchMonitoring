from typing import Iterable, Optional

from snmp.models import Device, Interface, MetricBinding


def get_active_bindings_for_device(device: Device) -> Iterable[MetricBinding]:
    if not device.profile_id:
        return MetricBinding.objects.none()

    return (
        MetricBinding.objects
        .filter(profile_id=device.profile_id, enabled_by_default=True)
        .select_related('metric', 'profile')
        .order_by('priority', 'id')
    )


def get_bindings_for_metric(device: Device, metric_key: str) -> Iterable[MetricBinding]:
    if not device.profile_id:
        return MetricBinding.objects.none()

    return (
        MetricBinding.objects
        .filter(profile_id=device.profile_id, metric__key=metric_key)
        .select_related('metric', 'profile')
        .order_by('priority', 'id')
    )


def resolve_best_binding(
    device: Device,
    metric_key: str,
    interface: Optional[Interface] = None,
) -> Optional[MetricBinding]:
    bindings = list(get_bindings_for_metric(device=device, metric_key=metric_key))
    if not bindings:
        return None

    if interface is None:
        for b in bindings:
            if b.index_strategy != MetricBinding.IndexStrategy.IF_INDEX:
                return b
    return bindings[0]
