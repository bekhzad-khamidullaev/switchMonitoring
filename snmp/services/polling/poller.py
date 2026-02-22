import logging
import time
from typing import List

from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from ping3 import ping

from snmp.models import Device, DevicePort, MetricSample, MetricSubscription
from snmp.services.discovery.read_base_snmp import snmp_get_many
from snmp.services.metrics.runtime import apply_converter, render_oid, validate_numeric
from snmp.services.alerting.evaluator import evaluate_subscription_thresholds
from snmp.services.observability.metrics import record_poll_metrics

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 120
ICMP_BINDING_SENTINEL = '__icmp_ping__'
PORT_RX_SIGNAL_SENTINEL = '__port_rx_signal__'
PORT_TX_SIGNAL_SENTINEL = '__port_tx_signal__'


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
        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            logger.warning('poll skipped because device does not exist', extra={'device_id': device_id})
            return 0
        subscriptions = list(
            MetricSubscription.objects
            .filter(device=device, enabled=True)
            .select_related('metric', 'binding', 'interface')
            .annotate(last_sample_ts=Max('samples__ts'))
        )

        samples: List[MetricSample] = []
        resolved = []
        icmp_subscriptions = []
        port_signal_subscriptions = []
        now = timezone.now()
        for subscription in subscriptions:
            interval = subscription.poll_interval_sec or subscription.metric.default_interval_sec
            if subscription.last_sample_ts and interval:
                elapsed = (now - subscription.last_sample_ts).total_seconds()
                if elapsed < interval:
                    continue
            if not subscription.binding_id:
                continue
            try:
                if subscription.binding and subscription.binding.oid_template == ICMP_BINDING_SENTINEL:
                    icmp_subscriptions.append(subscription)
                    continue
                if subscription.binding and subscription.binding.oid_template in {
                    PORT_RX_SIGNAL_SENTINEL,
                    PORT_TX_SIGNAL_SENTINEL,
                }:
                    port_signal_subscriptions.append(subscription)
                    continue
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
        community = device.effective_snmp_community()
        unique_oids = sorted({item[1] for item in resolved})
        if unique_oids:
            oid_to_value = snmp_get_many(
                ip=str(device.ip),
                community=community,
                oids=unique_oids,
                timeout=timeout,
                retries=retries,
            )

        if icmp_subscriptions:
            try:
                latency_seconds = ping(str(device.ip), timeout=timeout, unit='s')
            except Exception as exc:
                for subscription in icmp_subscriptions:
                    samples.append(
                        MetricSample(
                            subscription=subscription,
                            value_text='',
                            quality=MetricSample.Quality.BAD,
                            raw_value=str(exc),
                        )
                    )
            else:
                if latency_seconds in (None, False):
                    for subscription in icmp_subscriptions:
                        samples.append(
                            MetricSample(
                                subscription=subscription,
                                value_text='',
                                quality=MetricSample.Quality.BAD,
                                raw_value='timeout',
                            )
                        )
                else:
                    latency_ms = float(latency_seconds) * 1000.0
                    for subscription in icmp_subscriptions:
                        samples.append(
                            MetricSample(
                                subscription=subscription,
                                value_float=latency_ms,
                                value_text='',
                                quality=MetricSample.Quality.GOOD,
                                raw_value=str(latency_seconds),
                            )
                            )

        if port_signal_subscriptions:
            ports = {
                p.port: p
                for p in DevicePort.objects.filter(managed_device=device).only('port', 'rx_signal', 'tx_signal')
            }
            for subscription in port_signal_subscriptions:
                if_index = subscription.interface.if_index if subscription.interface_id and subscription.interface else None
                if if_index is None:
                    samples.append(
                        MetricSample(
                            subscription=subscription,
                            value_text='',
                            quality=MetricSample.Quality.BAD,
                            raw_value='interface is required',
                        )
                    )
                    continue
                port = ports.get(if_index)
                if not port:
                    samples.append(
                        MetricSample(
                            subscription=subscription,
                            value_text='',
                            quality=MetricSample.Quality.BAD,
                            raw_value='port data is missing',
                        )
                    )
                    continue
                if subscription.binding.oid_template == PORT_RX_SIGNAL_SENTINEL:
                    signal_value = port.rx_signal
                else:
                    signal_value = port.tx_signal
                if signal_value is None:
                    samples.append(
                        MetricSample(
                            subscription=subscription,
                            value_text='',
                            quality=MetricSample.Quality.UNKNOWN,
                            raw_value='no signal',
                        )
                    )
                    continue
                samples.append(
                    MetricSample(
                        subscription=subscription,
                        value_float=float(signal_value),
                        value_text='',
                        quality=MetricSample.Quality.GOOD,
                        raw_value=str(signal_value),
                    )
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

        for sample in samples:
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
