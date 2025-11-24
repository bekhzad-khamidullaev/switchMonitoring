"""
API URL patterns for SNMP monitoring system.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views.api_views import (
    SwitchViewSet, BranchViewSet, VendorViewSet, SwitchModelViewSet,
    MonitoringAPIView, MetricsAPIView, HealthCheckAPIView
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'switches', SwitchViewSet, basename='api-switch')
router.register(r'branches', BranchViewSet, basename='api-branch')
router.register(r'vendors', VendorViewSet, basename='api-vendor')
router.register(r'models', SwitchModelViewSet, basename='api-switchmodel')

# API URL patterns
urlpatterns = [
    # Authentication
    path('auth/token/', obtain_auth_token, name='api-token-auth'),
    
    # Main API routes
    path('', include(router.urls)),
    
    # Custom API endpoints
    path('monitoring/', MonitoringAPIView.as_view(), name='api-monitoring'),
    path('metrics/', MetricsAPIView.as_view(), name='api-metrics'),
    path('health-check/', HealthCheckAPIView.as_view(), name='api-health-check'),
    
    # DRF browsable API authentication
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
]