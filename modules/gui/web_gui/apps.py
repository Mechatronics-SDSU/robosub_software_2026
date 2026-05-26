import os, sys, subprocess
from django.apps                    import AppConfig
from django.conf                    import settings

"""
    discord: @314_piekitty
    github: @malaikajoiner
    
    from Django template.
    added stuff: ready() for writing test values... not really important
"""

class Web_UIConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'web_gui'
