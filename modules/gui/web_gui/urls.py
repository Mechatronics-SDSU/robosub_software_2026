from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('view_telemetry/', views.view_telemetry, name='view_telemetry'),
    path('get_telemetry/', views.get_telemetry, name='get_telemetry'),
    path('test_telemetry/', views.test_telemetry, name = 'test_telemetry'),
    path('DVLreset/', views.DVLreset, name = 'DVLreset'),
    path('recieveMemory/', views.recieveMemory, name = 'recieveMemory')
]