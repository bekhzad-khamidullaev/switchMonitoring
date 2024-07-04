from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('snmp/', include('snmp.urls')),
    path('outsource/', include('zabbixapp.urls')),
    path('olt/', include('olt_monitoring.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
