"""snmp.api.urls

Router for the REST API aligned with current models.

Base prefix in project: /api/v1/
"""

from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from snmp.api.views import (
    ATSViewSet,
    BranchViewSet,
    HostGroupViewSet,
    VendorViewSet,
    SwitchModelViewSet,
    SwitchViewSet,
    InterfaceViewSet,
    NeighborLinkViewSet,
    InterfaceBandwidthSampleViewSet,
    DashboardViewSet,
)

router = DefaultRouter()
router.register(r"ats", ATSViewSet, basename="ats")
router.register(r"branches", BranchViewSet, basename="branches")
router.register(r"host-groups", HostGroupViewSet, basename="host-groups")
router.register(r"vendors", VendorViewSet, basename="vendors")
router.register(r"switch-models", SwitchModelViewSet, basename="switch-models")
router.register(r"switches", SwitchViewSet, basename="switches")
router.register(r"interfaces", InterfaceViewSet, basename="interfaces")
router.register(r"neighbors", NeighborLinkViewSet, basename="neighbors")
router.register(r"bandwidth", InterfaceBandwidthSampleViewSet, basename="bandwidth")
router.register(r"dashboard", DashboardViewSet, basename="dashboard")

schema_view = get_schema_view(
    openapi.Info(
        title="SNMP Network Management API",
        default_version="v1",
        description="REST API for SNMP monitoring system",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Docs
    path("docs/", schema_view.with_ui("swagger", cache_timeout=0), name="api-docs"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="api-redoc"),
    path("swagger.json", schema_view.without_ui(cache_timeout=0), name="api-schema"),

    # JWT
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # API
    path("", include(router.urls)),
]
