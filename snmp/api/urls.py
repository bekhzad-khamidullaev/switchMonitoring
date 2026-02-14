from django.urls import path

from .views import (
    api_device_discover,
    api_device_metrics,
    api_device_onboard,
    api_device_timeseries,
    api_subscription_update,
)

urlpatterns = [
    path('devices/onboard', api_device_onboard, name='api_device_onboard'),
    path('devices/<int:device_id>/discover', api_device_discover, name='api_device_discover'),
    path('devices/<int:device_id>/metrics', api_device_metrics, name='api_device_metrics'),
    path('subscriptions/<int:subscription_id>', api_subscription_update, name='api_subscription_update'),
    path('devices/<int:device_id>/timeseries', api_device_timeseries, name='api_device_timeseries'),
]
