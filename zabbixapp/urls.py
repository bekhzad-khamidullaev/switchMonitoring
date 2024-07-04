from django.urls import path
from . import views

urlpatterns = [
    path('hosts/', views.hosts_view, name='hosts'),
    path('metrics/<int:host_id>/', views.metrics_view, name='metrics'),
]
