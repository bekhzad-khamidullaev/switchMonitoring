from django.urls import path
from snmp.views.switch_list import switch_list
from snmp.views.switch_detail import switch_detail
from snmp.views.port_traffic_data import port_traffic_data
from snmp.views.port_chart_partial import port_chart_partial

urlpatterns = [
    path('switches/', switch_list, name='switch_list'),
    path('switches/<int:pk>/', switch_detail, name='switch_detail'),
    path('ports/<int:port_id>/traffic/', port_traffic_data, name='port_traffic_data'),
    path('ports/<int:port_id>/chart/', port_chart_partial, name='port_chart_partial'),
]
