"""
API views for SNMP monitoring system.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.core.cache import cache
from django.utils import timezone

from ..models import Switch, Branch, SwitchModel, Vendor
from ..serializers import (
    SwitchSerializer, BranchSerializer, 
    SwitchModelSerializer, VendorSerializer
)
from ..services import SwitchService, MonitoringService, SNMPService


class SwitchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Switch model with full CRUD operations.
    """
    serializer_class = SwitchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'branch', 'model__vendor']
    search_fields = ['hostname', 'ip', 'model__device_model']
    ordering_fields = ['hostname', 'ip', 'status', 'last_update']
    ordering = ['-last_update']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.switch_service = SwitchService()
    
    def get_queryset(self):
        """Get switches filtered by user permissions."""
        return self.switch_service.get_switches_for_user(self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create new switch with validation."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Use service layer for creation
            switch, error = self.switch_service.create_switch(serializer.validated_data)
            if error:
                return Response(
                    {'error': error}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            response_serializer = self.get_serializer(switch)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """Update switch with validation."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            # Use service layer for update
            success, error = self.switch_service.update_switch(instance, serializer.validated_data)
            if not success:
                return Response(
                    {'error': error}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Refresh from database
            instance.refresh_from_db()
            response_serializer = self.get_serializer(instance)
            return Response(response_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def health_check(self, request, pk=None):
        """Perform health check on specific switch."""
        switch = self.get_object()
        monitoring_service = MonitoringService()
        
        health_report = monitoring_service.check_switch_health(switch)
        return Response(health_report)
    
    @action(detail=True, methods=['post'])
    def test_connectivity(self, request, pk=None):
        """Test connectivity to specific switch."""
        switch = self.get_object()
        snmp_service = SNMPService()
        
        connectivity_result = snmp_service.test_connectivity(
            switch.ip, 
            switch.snmp_community_ro
        )
        return Response(connectivity_result)
    
    @action(detail=True, methods=['post'])
    def discover_info(self, request, pk=None):
        """Auto-discover switch information."""
        switch = self.get_object()
        discovery_result = self.switch_service.auto_discover_switch_info(switch)
        return Response(discovery_result)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get switch statistics for the user."""
        stats = self.switch_service.get_switch_statistics(request.user)
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def offline(self, request):
        """Get offline switches."""
        offline_switches = self.get_queryset().filter(status=False)
        page = self.paginate_queryset(offline_switches)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(offline_switches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def high_signal(self, request):
        """Get switches with high signal levels."""
        threshold = float(request.query_params.get('threshold', -15))
        high_signal_switches = self.get_queryset().filter(
            models.Q(rx_signal__gt=threshold) | models.Q(tx_signal__gt=threshold)
        )
        
        page = self.paginate_queryset(high_signal_switches)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(high_signal_switches, many=True)
        return Response(serializer.data)


class BranchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Branch model.
    """
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name']
    ordering = ['name']
    
    @action(detail=True, methods=['get'])
    def switches(self, request, pk=None):
        """Get switches in this branch."""
        branch = self.get_object()
        switch_service = SwitchService()
        switches = switch_service.get_switches_for_user(request.user).filter(branch=branch)
        
        page = self.paginate_queryset(switches)
        if page is not None:
            serializer = SwitchSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = SwitchSerializer(switches, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get statistics for switches in this branch."""
        branch = self.get_object()
        switches = Switch.objects.filter(branch=branch)
        
        stats = {
            'total_switches': switches.count(),
            'online_switches': switches.filter(status=True).count(),
            'offline_switches': switches.filter(status=False).count(),
            'high_signal_switches': switches.filter(
                models.Q(rx_signal__gt=-15) | models.Q(tx_signal__gt=-15)
            ).count(),
        }
        
        if stats['total_switches'] > 0:
            stats['online_percentage'] = round(
                (stats['online_switches'] / stats['total_switches']) * 100, 2
            )
        else:
            stats['online_percentage'] = 0
        
        return Response(stats)


class VendorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Vendor model.
    """
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name']
    ordering = ['name']


class SwitchModelViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for SwitchModel model.
    """
    queryset = SwitchModel.objects.select_related('vendor').all()
    serializer_class = SwitchModelSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['vendor']
    search_fields = ['device_model', 'vendor__name']
    ordering = ['vendor__name', 'device_model']


class MonitoringAPIView(APIView):
    """
    API view for monitoring and metrics data.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitoring_service = MonitoringService()
    
    def get(self, request):
        """Get system monitoring overview."""
        overview = self.monitoring_service.get_system_overview()
        return Response(overview)


class MetricsAPIView(APIView):
    """
    API view for system metrics.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get system metrics from cache."""
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'request_metrics': cache.get('request_metrics', {}),
            'performance_metrics': cache.get('performance_metrics', {}),
            'error_metrics': cache.get('error_metrics', {}),
        }
        
        return Response(metrics)


class HealthCheckAPIView(APIView):
    """
    API view for system health checks.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Run health checks on specified switches."""
        switch_ids = request.data.get('switch_ids', [])
        branch_id = request.data.get('branch_id')
        offline_only = request.data.get('offline_only', False)
        
        # Build queryset
        if switch_ids:
            switches = Switch.objects.filter(id__in=switch_ids)
        elif branch_id:
            switches = Switch.objects.filter(branch_id=branch_id)
        else:
            # Use service to get user's permitted switches
            switch_service = SwitchService()
            switches = switch_service.get_switches_for_user(request.user)
        
        if offline_only:
            switches = switches.filter(status=False)
        
        # Limit to prevent overload
        switches = switches[:50]  # Maximum 50 switches per request
        
        # Run health checks
        health_reports = []
        for switch in switches:
            health_report = self.monitoring_service.check_switch_health(switch)
            health_reports.append(health_report)
        
        # Generate notifications if requested
        send_alerts = request.data.get('send_alerts', False)
        notifications = None
        if send_alerts:
            notifications = self.monitoring_service.generate_alert_notifications(health_reports)
        
        return Response({
            'health_reports': health_reports,
            'summary': self._generate_summary(health_reports),
            'notifications': notifications
        })
    
    def _generate_summary(self, health_reports):
        """Generate summary of health check results."""
        summary = {
            'total_checked': len(health_reports),
            'healthy': 0,
            'warning': 0,
            'unhealthy': 0,
            'error': 0,
            'total_alerts': 0,
            'critical_alerts': 0
        }
        
        for report in health_reports:
            status = report.get('overall_status', 'error')
            summary[status] = summary.get(status, 0) + 1
            
            alerts = report.get('alerts', [])
            summary['total_alerts'] += len(alerts)
            summary['critical_alerts'] += len([a for a in alerts if a.get('level') == 'critical'])
        
        return summary