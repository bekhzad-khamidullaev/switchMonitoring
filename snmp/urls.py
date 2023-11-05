from django.urls import path
from . import views

urlpatterns = [
    # Switch views
    path('switches/', views.switches, name='switches'),
    path('switches/create/', views.switch_create, name='switch_create'),
    path('switches/<int:pk>/', views.switch_detail, name='switch_detail'),
    path('switches/<int:pk>/update/', views.switch_update, name='switch_update'),
    path('switches/<int:pk>/delete/', views.switch_delete, name='switch_delete'),

    # Olt views
    path('olts/', views.olts, name='olts'),
    path('olts/create/', views.olt_create, name='olt_create'),
    path('olts/<int:pk>/', views.olt_detail, name='olt_detail'),
    path('olts/<int:pk>/update/', views.olt_update, name='olt_update'),
    path('olts/<int:pk>/delete/', views.olt_delete, name='olt_delete'),
]
