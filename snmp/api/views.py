from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from snmp.models import Device, MetricSample, MetricSubscription, ManagedDevice as ManagedDeviceModel
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError
from .permissions import user_can_access_device, user_can_access_managed_device
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
    managed_device_id = serializer.validated_data.get('managed_device_id')
    managed_device = None

    if managed_device_id:
        managed_device = ManagedDeviceModel.objects.filter(pk=managed_device_id).first()
        if not managed_device:
            return Response({'detail': 'Managed device not found'}, status=status.HTTP_404_NOT_FOUND)
        if not user_can_access_managed_device(request.user, managed_device):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        if ip and managed_device.ip and str(ip) != str(managed_device.ip):
            return Response(
                {'detail': 'Provided ip does not match managed device ip'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ip = ip or managed_device.ip

    if not ip:
        return Response(
            {'detail': 'IP address is required and managed device has no IP'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    device, _ = Device.objects.get_or_create(
        ip=ip,
        defaults={
            'managed_device': managed_device,
            'hostname': managed_device.hostname if managed_device else '',
            'status': bool(managed_device.status) if managed_device else False,
        },
    )
    if managed_device and not device.managed_device_id:
        device.managed_device = managed_device
        device.save(update_fields=['managed_device'])

    return Response(DeviceSerializer(device).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_device_discover(request, device_id):
    device = Device.objects.filter(pk=device_id).select_related('managed_device').first()
    if not device:
        return Response({'detail': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
    if not user_can_access_device(request.user, device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    community = request.data.get('community') or device.effective_snmp_community()

    try:
        result = run_device_discovery(ip=str(device.ip), community=community, managed_device=device.managed_device)
    except SnmpReadError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_device_metrics(request, device_id):
    device = Device.objects.filter(pk=device_id).first()
    if not device:
        return Response({'detail': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
    if not user_can_access_device(request.user, device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    subscriptions = (
        MetricSubscription.objects
        .filter(device=device)
        .select_related('metric', 'interface', 'binding')
        .order_by('interface__if_index', 'metric__key')
    )
    return Response(MetricSubscriptionSerializer(subscriptions, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_subscription_update(request, subscription_id):
    subscription = (
        MetricSubscription.objects
        .filter(pk=subscription_id)
        .select_related('device', 'device__managed_device', 'binding')
        .first()
    )
    if not subscription:
        return Response({'detail': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
    if not user_can_access_device(request.user, subscription.device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    serializer = MetricSubscriptionPatchSerializer(instance=subscription, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    warn = serializer.validated_data.get('warn_threshold', subscription.warn_threshold)
    crit = serializer.validated_data.get('crit_threshold', subscription.crit_threshold)
    if warn is not None and crit is not None:
        direction = 'lower_is_worse'
        if subscription.binding_id:
            direction = subscription.binding.binding_params.get('threshold_direction', direction)
        if direction == 'higher_is_worse' and crit < warn:
            return Response({'detail': 'crit_threshold must be >= warn_threshold'}, status=status.HTTP_400_BAD_REQUEST)
        if direction != 'higher_is_worse' and crit > warn:
            return Response({'detail': 'crit_threshold must be <= warn_threshold'}, status=status.HTTP_400_BAD_REQUEST)

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

    device = Device.objects.filter(pk=device_id).first()
    if not device:
        return Response({'detail': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
    if not user_can_access_device(request.user, device):
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    samples = MetricSample.objects.filter(subscription__device=device).select_related('subscription', 'subscription__metric', 'subscription__interface')

    if metric_key:
        samples = samples.filter(subscription__metric__key=metric_key)
    if if_index is not None:
        samples = samples.filter(subscription__interface__if_index=if_index)

    samples = samples.order_by('-ts')[: max(1, min(limit, 2000))]
    return Response(MetricSampleSerializer(samples, many=True).data)
