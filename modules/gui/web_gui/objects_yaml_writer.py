import time, os, threading

from multiprocessing                import Value
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
        self.file = os.environ.get("OBJECTS_YAML_FILE", os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../..", "objects.yaml"))) 

        with open(self.file, "r") as f:
            load = yaml.load(f) or {}

        self.data = load 
        course = self.data["course"]
        motor_factor = self.data["motor_factor"]
        mode_list = self.data["mode_list"]
        pid = self.data["pid"]
        
        if course not in self.data:
            raise KeyError(f"Course '{course}' not in objects.yaml")
        
        course_data = self.data[course]
        gate   = course_data.setdefault("gate", {})
        slalom = course_data.setdefault("slalom", {})
        octagon= course_data.setdefault("octagon", {})
        re    = course_data.setdefault("return", {})

        #initializes values if there is not currently any in objects.yaml
        
        self.gate_x_buf         = Value('d', float(gate.get("x_buf", 0.3)))
        self.gate_y_buf         = Value('d', float(gate.get("y_buf", 0.3)))
        self.gate_z_buf         = Value('d', float(gate.get("z_buf", 0.3)))
        self.gate_x             = Value('d', float(gate.get("x", 1.0)))
        self.gate_y             = Value('d', float(gate.get("y", 0.0)))
        self.gate_z             = Value('d', float(gate.get("z", 0.7)))
        self.gate_drop          = Value('d', float(gate.get("drop", 0.3)))
        self.gate_t_drop        = Value('d', float(gate.get("t_drop", 0.25)))

        self.slalom_x_buf       = Value('d', float(slalom.get("x_buf", 0.3)))
        self.slalom_y_buf       = Value('d', float(slalom.get("y_buf", 0.3)))
        self.slalom_z_buf       = Value('d', float(slalom.get("z_buf", 1.0)))
        self.slalom_z           = Value('d', float(slalom.get("z", 0.7)))
        self.slalom_x1          = Value('d', float(slalom.get("x1", 2.0)))
        self.slalom_y1          = Value('d', float(slalom.get("y1", 0.0)))
        self.slalom_x2          = Value('d', float(slalom.get("x2", 2.5)))
        self.slalom_y2          = Value('d', float(slalom.get("y2", -0.5)))
        self.slalom_x3          = Value('d', float(slalom.get("x3", 3.0)))
        self.slalom_y3          = Value('d', float(slalom.get("y3", 0.0)))

        self.octagon_x_buf      = Value('d', float(octagon.get("x_buf", 0.3)))
        self.octagon_y_buf      = Value('d', float(octagon.get("y_buf", 0.3)))
        self.octagon_z_buf      = Value('d', float(octagon.get("z_buf", 0.3)))
        self.octagon_x          = Value('d', float(octagon.get("x", 4.0)))
        self.octagon_y          = Value('d', float(octagon.get("y", 0.0)))
        self.octagon_z          = Value('d', float(octagon.get("z", -0.3)))
        self.octagon_pause      = Value('d', float(octagon.get("pause", 5.0)))
        self.octagon_depth      = Value('d', float(octagon.get("depth", 0.7)))
        self.octagon_angle      = Value('d', float(octagon.get("angle", -45.0)))

        self.return_x_buf       = Value('d', float(re.get("x_buf", 0.3)))
        self.return_y_buf       = Value('d', float(re.get("y_buf", 0.3)))
        self.return_z_buf       = Value('d', float(re.get("z_buf", 1.0)))
        self.return_x1          = Value('d', float(re.get("x1", 3.0)))
        self.return_y1          = Value('d', float(re.get("y1", 0.0)))
        self.return_x2          = Value('d', float(re.get("x2", 2.0)))
        self.return_y2          = Value('d', float(re.get("y2", 0.5)))
        self.return_drop        = Value('d', float(re.get("drop", 0.3)))
        self.return_t_drop      = Value('d', float(re.get("t_drop", 0.25)))
        self.return_depth       = Value('d', float(re.get("depth", 0.7)))

        self.lock = threading.Lock()
        self.write_values()

    def write_values(self):
            with self.lock:                          
                course = self.data.get("course", "jesse_pool") #jesse pool set as default course
                course_data = self.data.setdefault(course, {})
                course_data.setdefault("gate", {})
                course_data.setdefault("slalom", {})
                course_data.setdefault("octagon", {})
                course_data.setdefault("return", {})


                self.data[course]["gate"]["x_buf"] = float(self.gate_x_buf.value)
                self.data[course]["gate"]["y_buf"] = float(self.gate_y_buf.value)
                self.data[course]["gate"]["z_buf"] = float(self.gate_z_buf.value)
                self.data[course]["gate"]["x"] = float(self.gate_x.value)
                self.data[course]["gate"]["y"] = float(self.gate_y.value)
                self.data[course]["gate"]["z"] = float(self.gate_z.value)
                self.data[course]["gate"]["drop"] = float(self.gate_drop.value)
                self.data[course]["gate"]["t_drop"] = float(self.gate_t_drop.value)

                self.data[course]["slalom"]["x_buf"] = float(self.slalom_x_buf.value)
                self.data[course]["slalom"]["y_buf"] = float(self.slalom_y_buf.value)
                self.data[course]["slalom"]["z_buf"] = float(self.slalom_z_buf.value)
                self.data[course]["slalom"]["z"] = float(self.slalom_z.value)
                self.data[course]["slalom"]["x1"] = float(self.slalom_x1.value)
                self.data[course]["slalom"]["y1"] = float(self.slalom_y1.value)
                self.data[course]["slalom"]["x2"] = float(self.slalom_x2.value)
                self.data[course]["slalom"]["y2"] = float(self.slalom_y2.value)
                self.data[course]["slalom"]["x3"] = float(self.slalom_x3.value)
                self.data[course]["slalom"]["y3"] = float(self.slalom_y3.value)

                self.data[course]["octagon"]["x_buf"] = float(self.octagon_x_buf.value)
                self.data[course]["octagon"]["y_buf"] = float(self.octagon_y_buf.value)
                self.data[course]["octagon"]["z_buf"] = float(self.octagon_z_buf.value)
                self.data[course]["octagon"]["x"] = float(self.octagon_x.value)
                self.data[course]["octagon"]["y"] = float(self.octagon_y.value)
                self.data[course]["octagon"]["z"] = float(self.octagon_z.value)
                self.data[course]["octagon"]["pause"] = float(self.octagon_pause.value)
                self.data[course]["octagon"]["depth"] = float(self.octagon_depth.value)
                self.data[course]["octagon"]["angle"] = float(self.octagon_angle.value)

                self.data[course]["return"]["x_buf"] = float(self.return_x_buf.value)
                self.data[course]["return"]["y_buf"] = float(self.return_y_buf.value)
                self.data[course]["return"]["z_buf"] = float(self.return_z_buf.value)
                self.data[course]["return"]["x1"] = float(self.return_x1.value)
                self.data[course]["return"]["y1"] = float(self.return_y1.value)
                self.data[course]["return"]["x2"] = float(self.return_x2.value)
                self.data[course]["return"]["y2"] = float(self.return_y2.value)  
                self.data[course]["return"]["drop"] = float(self.return_drop.value)
                self.data[course]["return"]["t_drop"] = float(self.return_t_drop.value)
                self.data[course]["return"]["depth"] = float(self.return_depth.value)

                tmp = self.file + ".tmp"
                with open(tmp, "w") as f:
                    yaml.dump(self.data, f)
                os.replace(tmp, self.file)

