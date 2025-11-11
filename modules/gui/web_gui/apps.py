from django.apps import AppConfig
from django.conf import settings
import os, sys, subprocess

class Web_UIConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'web_gui'

    def ready(self):      
        #(writes fake values to telemetry.json)
        testing_path = os.path.join(os.path.dirname(__file__), "testing/testing_values.py")
        telemetryJsonFile = os.path.join(settings.BASE_DIR, "testVals.json")
        env = {**os.environ, "TEST_FILE": telemetryJsonFile}
        subprocess.Popen([sys.executable, testing_path], env=env)