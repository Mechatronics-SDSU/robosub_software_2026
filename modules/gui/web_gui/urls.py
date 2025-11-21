from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('view_telemetry/', views.view_telemetry, name='view_telemetry'),
    path('get_telemetry/', views.get_telemetry, name='get_telemetry'),
    path('test_telemetry/', views.test_telemetry, name = 'test_telemetry'),
    path('DVLreset/', views.DVLreset, name = 'DVLreset'),
    path('recieveMemory/', views.recieveMemory, name = 'recieveMemory'),
    path('launch/', views.launch, name = 'launch'),
    path('start_button/', views.start_button, name = 'start_button'),
    path('hard_kill/', views.hard_kill, name = 'hard_kill'),
    path('soft_kill/', views.soft_kill, name = 'soft_kill')
]