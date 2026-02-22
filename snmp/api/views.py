from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from snmp.models import Device, MetricSample, MetricSubscription
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError

from .permissions import user_can_access_device, user_can_create_device, user_can_manage_device
from .serializers import (
    DeviceOnboardSerializer,
    DeviceSerializer,
    MetricSampleSerializer,
    MetricSubscriptionPatchSerializer,
    MetricSubscriptionSerializer,
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_device_onboard(request):
    serializer = DeviceOnboardSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    ip = serializer.validated_data.get('ip')
    device_id = serializer.validated_data.get('device_id')

    if device_id:
        device = get_object_or_404(Device.objects.only('id', 'ip', 'group_id'), pk=device_id)
        if not user_can_access_device(request.user, device):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        if ip and device.ip and str(ip) != str(device.ip):
            return Response(
                {'detail': 'Provided ip does not match device ip'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ip = ip or device.ip
    else:
        device = Device.objects.only('id', 'ip', 'group_id').filter(ip=ip).first()

    if device and not user_can_access_device(request.user, device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    if not device and ip:
        if not user_can_create_device(request.user):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        try:
            with transaction.atomic():
                device = Device.objects.create(ip=ip)
        except IntegrityError:
            # Idempotent create under concurrent onboard calls for the same IP.
            device = Device.objects.only('id', 'ip', 'group_id').get(ip=ip)

    if not device:
        return Response({'detail': 'IP or Device ID required'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(DeviceSerializer(device).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_device_discover(request, device_id):
    device = get_object_or_404(Device, pk=device_id)
    if not user_can_manage_device(request.user, device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    community = request.data.get('community') or device.effective_snmp_community()

    try:
        result = run_device_discovery(ip=str(device.ip), community=community, managed_device=device)
    except SnmpReadError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_device_metrics(request, device_id):
    try:
        limit = int(request.query_params.get('limit', '1000'))
    except (TypeError, ValueError):
        return Response({'detail': 'limit must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        offset = int(request.query_params.get('offset', '0'))
    except (TypeError, ValueError):
        return Response({'detail': 'offset must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

    enabled_raw = request.query_params.get('enabled')
    if enabled_raw is None:
        enabled_filter = None
    elif enabled_raw.lower() in {'1', 'true', 'yes'}:
        enabled_filter = True
    elif enabled_raw.lower() in {'0', 'false', 'no'}:
        enabled_filter = False
    else:
        return Response({'detail': 'enabled must be boolean'}, status=status.HTTP_400_BAD_REQUEST)

    device = get_object_or_404(Device.objects.only('id', 'group_id'), pk=device_id)
    if not user_can_access_device(request.user, device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    limit = max(1, min(limit, 5000))
    offset = max(0, min(offset, 20000))

    subscriptions_qs = (
        MetricSubscription.objects.filter(device=device)
        .select_related('metric', 'interface', 'binding')
        .order_by('interface__if_index', 'metric__key')
    )
    if enabled_filter is not None:
        subscriptions_qs = subscriptions_qs.filter(enabled=enabled_filter)
    subscriptions = subscriptions_qs[offset:offset + limit]
    return Response(MetricSubscriptionSerializer(subscriptions, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_subscription_update(request, subscription_id):
    subscription = (
        MetricSubscription.objects
        .filter(pk=subscription_id)
        .select_related('device', 'binding')
        .first()
    )
    if not subscription:
        return Response({'detail': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
    if not user_can_manage_device(request.user, subscription.device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    serializer = MetricSubscriptionPatchSerializer(instance=subscription, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    warn = serializer.validated_data.get('warn_threshold', subscription.warn_threshold)
    crit = serializer.validated_data.get('crit_threshold', subscription.crit_threshold)
    threshold_error = subscription.validate_thresholds(warn_value=warn, crit_value=crit)
    if threshold_error:
        return Response({'detail': threshold_error}, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(MetricSubscriptionSerializer(subscription).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_device_timeseries(request, device_id):
    metric_key = request.query_params.get('metric')
    if_index = request.query_params.get('if_index')
    try:
        limit = int(request.query_params.get('limit', '200'))
    except (TypeError, ValueError):
        return Response({'detail': 'limit must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
    if limit < 1 or limit > 5000:
        return Response({'detail': 'limit must be between 1 and 5000'}, status=status.HTTP_400_BAD_REQUEST)

    if if_index is not None:
        try:
            if_index = int(if_index)
        except (TypeError, ValueError):
            return Response({'detail': 'if_index must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

    before = request.query_params.get('before')
    before_dt = None
    if before:
        before_dt = parse_datetime(before)
        if before_dt is None:
            return Response({'detail': 'before must be an ISO-8601 datetime'}, status=status.HTTP_400_BAD_REQUEST)

    device = get_object_or_404(Device.objects.only('id', 'group_id'), pk=device_id)
    if not user_can_access_device(request.user, device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    samples = (
        MetricSample.objects
        .filter(device=device)
        .select_related('subscription', 'subscription__metric', 'subscription__interface')
    )

    if metric_key:
        samples = samples.filter(subscription__metric__key=metric_key)
    if if_index is not None:
        samples = samples.filter(subscription__interface__if_index=if_index)
    if before_dt:
        samples = samples.filter(ts__lt=before_dt)

    samples = samples.order_by('-ts', '-id')[:limit]
    return Response(MetricSampleSerializer(samples, many=True).data)
