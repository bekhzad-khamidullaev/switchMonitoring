import logging
import time
from typing import List

from django.core.cache import cache
from django.db import transaction

from snmp.models import Device, MetricSample, MetricSubscription
from snmp.services.discovery.read_base_snmp import snmp_get_many
from snmp.services.metrics.runtime import apply_converter, render_oid, validate_numeric
from snmp.services.alerting.evaluator import evaluate_subscription_thresholds
from snmp.services.observability.metrics import record_poll_metrics

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 120


def _lock_key(device_id: int) -> str:
    return f'poll_device_metrics_lock:{device_id}'


def _acquire_lock(device_id: int) -> bool:
    return cache.add(_lock_key(device_id), '1', LOCK_TTL_SECONDS)


def _release_lock(device_id: int) -> None:
    cache.delete(_lock_key(device_id))


def poll_device_metrics(device_id: int, timeout: int = 2, retries: int = 1) -> int:
    if not _acquire_lock(device_id):
        logger.info('poll skipped because lock is active', extra={'device_id': device_id})
        return 0

    started = time.monotonic()
    snmp_errors = 0
    saved_count = 0
    try:
        device = Device.objects.get(pk=device_id)
        subscriptions = list(
            MetricSubscription.objects
            .filter(device=device, enabled=True)
            .select_related('metric', 'binding', 'interface')
        )

        samples: List[MetricSample] = []
        resolved = []
        for subscription in subscriptions:
            if not subscription.binding_id:
                continue
            try:
                oid_resolution = render_oid(
                    binding=subscription.binding,
                    device=device,
                    interface=subscription.interface,
                )
                resolved.append((subscription, oid_resolution.oid))
            except ValueError as exc:
                samples.append(
                    MetricSample(
                        subscription=subscription,
                        value_text='',
                        quality=MetricSample.Quality.BAD,
                        raw_value=str(exc),
                    )
                )

        oid_to_value = {}
        community = device.switch.snmp_community_ro if device.switch_id else 'public'
        unique_oids = sorted({item[1] for item in resolved})
        if unique_oids:
            oid_to_value = snmp_get_many(
                ip=str(device.ip),
                community=community,
                oids=unique_oids,
                timeout=timeout,
                retries=retries,
            )

        for subscription, oid in resolved:
            raw_result = oid_to_value.get(oid)
            if isinstance(raw_result, Exception):
                snmp_errors += 1
                samples.append(
                    MetricSample(
                        subscription=subscription,
                        value_text='',
                        quality=MetricSample.Quality.BAD,
                        raw_value=str(raw_result),
                    )
                )
                continue

            converted = apply_converter(
                converter=subscription.binding.converter,
                raw_value=raw_result,
                binding_params=subscription.binding.binding_params,
            )
            numeric_value = validate_numeric(
                value=converted,
                binding_params=subscription.binding.binding_params,
            )

            if numeric_value is not None:
                samples.append(
                    MetricSample(
                        subscription=subscription,
                        value_float=numeric_value,
                        value_text='',
                        quality=MetricSample.Quality.GOOD,
                        raw_value=str(raw_result),
                    )
                )
            else:
                text_value = '' if converted is None else str(converted)
                samples.append(
                    MetricSample(
                        subscription=subscription,
                        value_float=None,
                        value_text=text_value,
                        quality=MetricSample.Quality.GOOD if text_value else MetricSample.Quality.UNKNOWN,
                        raw_value=str(raw_result),
                    )
                )

        with transaction.atomic():
            MetricSample.objects.bulk_create(samples, batch_size=1000)

        saved_samples = list(
            MetricSample.objects
            .filter(subscription__device_id=device_id)
            .order_by('-id')[: len(samples)]
            .select_related('subscription', 'subscription__binding')
        )
        for sample in saved_samples:
            evaluate_subscription_thresholds(sample)

        logger.info(
            'poll completed',
            extra={
                'device_id': device_id,
                'subscriptions': len(subscriptions),
                'samples_saved': len(samples),
            },
        )
        saved_count = len(samples)
        return saved_count
    finally:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        record_poll_metrics(duration_ms=elapsed_ms, samples_saved=saved_count, snmp_errors=snmp_errors)
        _release_lock(device_id)
