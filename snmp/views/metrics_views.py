from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import csv

from snmp.models import Device, Interface, MetricBinding, MetricSubscription, Switch
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError
from snmp.services.metrics.registry import get_active_bindings_for_device
from snmp.services.polling.poller import poll_device_metrics


def _validate_thresholds(subscription: MetricSubscription, warn_value, crit_value):
    if warn_value is None or crit_value is None:
        return None

    direction = 'lower_is_worse'
    if subscription.binding_id:
        direction = subscription.binding.binding_params.get('threshold_direction', direction)

    if direction == 'higher_is_worse':
        if crit_value < warn_value:
            return 'Critical threshold must be greater than or equal to warning threshold.'
    else:
        if crit_value > warn_value:
            return 'Critical threshold must be less than or equal to warning threshold.'
    return None


@login_required
@permission_required('snmp.change_device', raise_exception=True)
def switch_metrics(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    device, _ = Device.objects.get_or_create(
        ip=switch.ip,
        defaults={
            'switch': switch,
            'hostname': switch.hostname or '',
            'status': bool(switch.status),
        },
    )
    if not device.switch_id:
        device.switch = switch
        device.save(update_fields=['switch'])

    bindings = list(get_active_bindings_for_device(device))
    interfaces = list(device.interfaces.order_by('if_index'))
    subscriptions = (
        MetricSubscription.objects
        .filter(device=device)
        .select_related('metric', 'interface', 'binding')
        .order_by('interface__if_index', 'metric__key')
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'run_discovery':
            community = request.POST.get('community', '').strip() or switch.snmp_community_ro or 'public'
            try:
                result = run_device_discovery(ip=str(switch.ip), community=community, switch=switch)
                messages.success(
                    request,
                    f"Discovery completed: interfaces={result.get('interfaces_count', 0)} profile_id={result.get('profile_id', 0)}",
                )
            except SnmpReadError as exc:
                messages.error(request, f"Discovery failed: {exc}")
            return redirect('switch_metrics', pk=switch.pk)

        if action == 'poll_now':
            saved_count = poll_device_metrics(device.id)
            messages.success(request, f'Polling completed. Saved samples: {saved_count}.')
            return redirect('switch_metrics', pk=switch.pk)

        if action == 'apply_profile':
            selected_binding_ids = request.POST.getlist('binding_ids')
            scope = request.POST.get('scope', 'optical')

            selected_bindings = [
                b for b in bindings if str(b.id) in selected_binding_ids
            ]
            if not selected_bindings:
                messages.warning(request, 'Select at least one metric binding.')
                return redirect('switch_metrics', pk=switch.pk)

            if scope == 'device':
                target_interfaces = [None]
            elif scope == 'all':
                target_interfaces = interfaces
            else:
                target_interfaces = [i for i in interfaces if i.is_optical]

            created_or_updated = 0
            for binding in selected_bindings:
                for interface in target_interfaces:
                    defaults = {
                        'binding': binding,
                        'enabled': True,
                        'poll_interval_sec': binding.metric.default_interval_sec,
                    }
                    if interface is None:
                        MetricSubscription.objects.update_or_create(
                            device=device,
                            interface__isnull=True,
                            metric=binding.metric,
                            defaults={
                                **defaults,
                                'interface': None,
                            },
                        )
                    else:
                        MetricSubscription.objects.update_or_create(
                            device=device,
                            interface=interface,
                            metric=binding.metric,
                            defaults=defaults,
                        )
                    created_or_updated += 1

            messages.success(request, f'Applied {created_or_updated} metric subscriptions.')
            return redirect('switch_metrics', pk=switch.pk)

    return render(
        request,
        'device_metrics.html',
        {
            'switch': switch,
            'device': device,
            'bindings': bindings,
            'interfaces': interfaces,
            'subscriptions': subscriptions,
        },
    )


@login_required
@permission_required('snmp.change_metricsubscription', raise_exception=True)
@require_POST
def update_metric_subscription(request, subscription_id):
    subscription = get_object_or_404(MetricSubscription, pk=subscription_id)

    subscription.enabled = request.POST.get('enabled') == 'on'

    warn = request.POST.get('warn_threshold', '').strip()
    crit = request.POST.get('crit_threshold', '').strip()
    poll = request.POST.get('poll_interval_sec', '').strip()

    try:
        subscription.warn_threshold = float(warn) if warn else None
        subscription.crit_threshold = float(crit) if crit else None
        subscription.poll_interval_sec = int(poll) if poll else None
    except ValueError:
        messages.error(request, 'Invalid numeric value in thresholds or poll interval.')
        switch_pk = subscription.device.switch_id
        if switch_pk:
            return redirect('switch_metrics', pk=switch_pk)
        return redirect('switches')

    threshold_error = _validate_thresholds(
        subscription=subscription,
        warn_value=subscription.warn_threshold,
        crit_value=subscription.crit_threshold,
    )
    if threshold_error:
        messages.error(request, threshold_error)
        switch_pk = subscription.device.switch_id
        if switch_pk:
            return redirect('switch_metrics', pk=switch_pk)
        return redirect('switches')
    subscription.save(update_fields=['enabled', 'warn_threshold', 'crit_threshold', 'poll_interval_sec'])

    messages.success(request, 'Subscription updated.')
    switch_pk = subscription.device.switch_id
    if switch_pk:
        return redirect('switch_metrics', pk=switch_pk)
    return redirect('switches')


@login_required
@permission_required('snmp.view_metricsample', raise_exception=True)
def export_device_metrics_csv(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    device = get_object_or_404(Device, switch=switch)

    metric = request.GET.get('metric', '').strip()
    if_index = request.GET.get('if_index', '').strip()
    limit = request.GET.get('limit', '1000').strip()

    try:
        limit_value = max(1, min(int(limit), 10000))
    except ValueError:
        limit_value = 1000

    queryset = (
        device.subscriptions
        .select_related('metric', 'interface')
        .prefetch_related('samples')
    )
    if metric:
        queryset = queryset.filter(metric__key=metric)
    if if_index:
        queryset = queryset.filter(interface__if_index=if_index)

    samples = []
    for sub in queryset:
        for sample in sub.samples.all().order_by('-ts')[:limit_value]:
            samples.append((sub, sample))

    samples.sort(key=lambda item: item[1].ts, reverse=True)
    samples = samples[:limit_value]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="device_{device.id}_metrics.csv"'
    writer = csv.writer(response)
    writer.writerow(['ts', 'metric', 'if_index', 'value_float', 'value_text', 'quality', 'raw_value'])
    for sub, sample in samples:
        writer.writerow([
            sample.ts.isoformat(),
            sub.metric.key,
            sub.interface.if_index if sub.interface_id else '',
            sample.value_float if sample.value_float is not None else '',
            sample.value_text,
            sample.quality,
            sample.raw_value,
        ])

    return response
