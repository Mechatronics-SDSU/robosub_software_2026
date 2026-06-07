import os, threading

from ruamel.yaml                    import YAML

"""
    discord: @314_piekitty
    github: @malaikajoiner
    
    Objects Yaml Writer holds all the values for pid and course data and writes it into objects.yaml
    There should only be one instance of an Objects Yaml Writer created in views.py 
    
"""

yaml = YAML()
yaml.preserve_quotes = True

class Yaml_writer:

    def __init__(self):
        self.file = os.environ.get(
            "OBJECTS_YAML_FILE",
            os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "../../..",
                    "objects.yaml"
                )
            )
        )

        with open(self.file, "r") as f:
            self.data = yaml.load(f) or {}

        self.lock = threading.Lock()


    def set_value(self, course, mode, key, val):
        with self.lock:
            self.data.setdefault(course, {})
            self.data[course].setdefault(mode, {})

            try:
                val = float(val)
            except ValueError:
                pass

            self.data[course][mode][key] = val

            tmp = self.file + ".tmp"
            with open(tmp, "w") as f:
                yaml.dump(self.data, f)
            os.replace(tmp, self.file)


   
