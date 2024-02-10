from django.urls import path
from . import views

urlpatterns = [
    path('switches/', views.switches, name='switches'),
    path('switches/create/', views.switch_create, name='switch_create'),
    path('switches/<int:pk>/', views.switch_detail, name='switch_detail'),
    path('switches/<int:pk>/update/', views.switch_update, name='switch_update'),
    path('switches/<int:pk>/delete/', views.switch_delete, name='switch_delete'),
    path('switches/switch_status/<int:pk>/', views.switch_status, name='switch_status'),
]
