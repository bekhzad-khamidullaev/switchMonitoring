from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from config.error_views import permission_denied_view
from config.health import healthcheck_view
from config.metrics import app_metrics_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', healthcheck_view, name='healthz'),
    path('metrics/app/', app_metrics_view, name='app_metrics'),
    path('', include('users.urls')),
    path('snmp/', include('snmp.urls')),
    # path('outsource/', include('zabbixapp.urls')),
    # path('olt/', include('olt_monitoring.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler403 = permission_denied_view
