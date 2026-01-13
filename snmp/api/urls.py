from rest_framework.routers import DefaultRouter

from snmp.api.views import SwitchViewSet, InterfaceViewSet, MacEntryViewSet, BandwidthSampleViewSet

router = DefaultRouter()
router.register(r'switches', SwitchViewSet, basename='switch')
router.register(r'interfaces', InterfaceViewSet, basename='interface')
router.register(r'mac', MacEntryViewSet, basename='mac')
router.register(r'bandwidth', BandwidthSampleViewSet, basename='bandwidth')

urlpatterns = router.urls
