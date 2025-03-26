
from django.urls import path
from .views.zabbix_sync import sync_hosts_from_zabbix

    
urlpatterns = [
    path('synch_zbx/', sync_hosts_from_zabbix, name='sync_zbx'),

]