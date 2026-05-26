from django.urls import path
from . import views

"""
    discord: @314_piekitty
    github: @malaikajoiner
    
    Django template for connecting html files to python functions in views.py
    
"""

urlpatterns = [
    path("", views.index, name="index"),
    path('change_color_mode/', views.change_color_mode, name='change_color_mode'),
    path('view_telemetry/', views.view_telemetry, name='view_telemetry'),
    path('get_telemetry/', views.get_telemetry, name='get_telemetry'),
    path('DVLreset/', views.DVLreset, name = 'DVLreset'),
    path('recieveMemory/', views.recieveMemory, name = 'recieveMemory'),
    path('launch/', views.launch, name = 'launch'),
    path('start_button/', views.start_button, name = 'start_button'),
    path('hard_kill/', views.hard_kill, name = 'hard_kill'),
    path('soft_kill/', views.soft_kill, name = 'soft_kill'),
    path('mission_planner/', views.mission_planner, name = 'mission_planner'),
    path('edit_courses/', views.edit_courses, name = 'edit_courses'),
    path('set_course/', views.set_course, name = 'set_course'),
    path('copy_yaml/', views.copy_yaml, name = 'copy_yaml'),
    path('set_objects_yaml_value/', views.set_objects_yaml_value, name = 'set_objects_yaml_value'),
    path('get_objects_yaml/', views.get_objects_yaml, name = 'get_objects_yaml'),
    path('send_objects_yaml/', views.send_objects_yaml, name = 'send_objects_yaml'),
    path('edit_mode_list/', views.edit_mode_list, name = 'edit_mode_list'),
    path('send_mode_list/', views.send_mode_list, name = 'send_mode_list'),
    path('add_mode/', views.add_mode, name = 'add_mode'),
    path('reset_mode_list/', views.reset_mode_list, name = 'reset_mode_list'),
    path('pid_tuning/', views.pid_tuning, name = 'pid_tuning'),
    path('get_pid/', views.get_pid, name = 'get_pid'),
    path('set_pid/', views.set_pid, name = 'set_pid'),
    path('reset_courses/', views.reset_courses, name = 'reset_courses'),
    path('get_motor/', views.get_motor, name = 'get_motor'),
    path('set_motor/', views.set_motor, name = 'set_motor')
]