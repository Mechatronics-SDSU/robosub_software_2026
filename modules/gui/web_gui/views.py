import socket, json, os, subprocess, sys

from django.shortcuts           import render, redirect
from django.http                import HttpResponse, JsonResponse
from django.conf                import settings
from io                         import StringIO
from pathlib                    import Path
from .objects_yaml_writer       import Yaml_writer
from ruamel.yaml                import YAML

try:
    from modules.sensors.a50_dvl.dvl import UDP_IP, UDP_PORT
except:
    print("UDP_IP and UDP_PORT not connected...")

"""
    discord: @314_piekitty
    github: @malaikajoiner
    
    File that handles most GUI related functions.
    
"""

yaml = YAML()
yaml.preserve_quotes = True
yaml_writer = Yaml_writer()
shared_memory_object = None
color_mode = "dark"  #dark vs pink mode for GUI colors

def recieveMemory(memory=None):
    #if called with argument, reassigns memory object. if called with no argument, returns the existing object
    global shared_memory_object
    if memory is None:
        return shared_memory_object
    shared_memory_object = memory
    return shared_memory_object

def index(request):
    #homepage render
    return render(request, 'index.html', {"color_mode": color_mode})

def change_color_mode(request):
    #changes colors to Pink mode and Dark mode
    global color_mode
    if (color_mode=="pink"): 
        color_mode = "dark"
    else:
        color_mode = "pink"
    return redirect(request.META.get("HTTP_REFERER", "/"))

def launch(request):
    #runs launch.py
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "launch.py"
    process = subprocess.Popen(
             [sys.executable, "-u", str(script)],
             cwd = str(repo_root)
    )
    return redirect("/")

def hard_kill(request):
    #runs stop alias
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "hard_kill.sh"
    process = subprocess.Popen(
             ["sh", str(script)],
             cwd = str(repo_root)
    )
    return redirect("/")

def soft_kill(request):
    #runs soft stop (code from launch.py)
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "soft_kill.py"
    process = subprocess.Popen(
             [sys.executable, "-u", str(script)],
             cwd = str(repo_root)
    )
    return redirect("/")

def start_button(request):
    #runs start_button.py
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "start_button.py"
    process = subprocess.Popen(
             [sys.executable, "-u", str(script)],
             cwd = str(repo_root)
    )
    return redirect("/")

def view_telemetry(request): 
    #telemetry page render
    return render(request, "telemetry.html", {"color_mode": color_mode})

SHARED_MEMORY_FILE = os.path.join(settings.BASE_DIR, "telemetry.json")
def get_telemetry(request):
    #Writes shared memory into a json file
    with open(SHARED_MEMORY_FILE, "r") as f:
        return JsonResponse(json.load(f))
    
def DVLreset(request):
        #Resets DVL values to 0
        serv_addr = (UDP_IP, UDP_PORT)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(serv_addr)
            json_command = {"command": "reset_dead_reckoning"}
            sock.send(json.dumps(json_command).encode())
            sock.close()
        except Exception as e:
            print("Failed to reset dead reckoning:", e)
        return redirect(request.META.get("HTTP_REFERER", "/"))

def mission_planner(request): 
    #mission planner page render
    global color_mode
    return render(request, "mission_planner.html", {"color_mode": color_mode})

def edit_courses(request): 
    #edit courses page render
    yamlfile = OBJECTS_YAML_FILE
    with open(yamlfile, "r") as f:
        data = yaml.load(f)
    course = data.get("course")
    courses = [ key for key, value in data.items()
                   if isinstance(value, dict)
                   and any(isinstance(v, dict) for v in value.values())
                ]
    objects = []
    for mode, values in data[course].items():
        if isinstance(values, dict):
            objects.append({
                    "mode": mode,
                    "val": list(values.items())
        })
    return render(request, "edit_courses.html", {"course": course, "color_mode": color_mode, "courses": courses, "objects": objects, "motor": data.get("motor_factor")})

OBJECTS_YAML_RESET = Path(settings.BASE_DIR).parent.parent / "modules/objects_yaml_COPIES/default.yaml"
def reset_courses(request):
    global yaml_writer 

    with yaml_writer.lock:
        with open(OBJECTS_YAML_RESET, "r") as f:
                load = yaml.load(f) or {}
        
        yaml_writer.data = load

        tmp = yaml_writer.file + ".tmp"
        with open(tmp, "w") as f:
            yaml.dump(yaml_writer.data, f)
        os.replace(tmp, yaml_writer.file)
    return redirect(request.META.get("HTTP_REFERER", "/"))

def get_motor(request):
    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}
    text = data.get("motor_factor")
    return HttpResponse(str(text), content_type="text/plain")

def set_motor(request):
    mf = float(request.GET.get("motor"))

    with yaml_writer.lock:

        yaml_writer.data["motor_factor"] = mf

        tmp = yaml_writer.file + ".tmp"
        with open(tmp, "w") as f:
            yaml.dump(yaml_writer.data, f)
        os.replace(tmp, yaml_writer.file)

    return redirect(request.META.get("HTTP_REFERER", "/"))

def set_objects_yaml_value(request):
    #Changes values in objects.yaml based on course, name, and value input
    global yaml_writer 
    val = float(request.GET.get("val"))
    course = request.GET.get("course")
    mode = request.GET.get("mode")
    key = request.GET.get("key")

    with yaml_writer.lock:

        yaml_writer.data["course"] = course

        yaml_writer.data.setdefault(course, {}).setdefault(mode, {})
        yaml_writer.data[course][mode][key] = val

        tmp = yaml_writer.file + ".tmp"
        with open(tmp, "w") as f:
            yaml.dump(yaml_writer.data, f)
        os.replace(tmp, yaml_writer.file)

    return redirect(request.META.get("HTTP_REFERER", "/"))

def set_course(request):
    #changes course in objects.yaml
    global yaml_writer
    course = request.GET.get("course")

    with yaml_writer.lock:

        yaml_writer.data["course"] = course

        tmp = yaml_writer.file + ".tmp"
        with open(tmp, "w") as f:
            yaml.dump(yaml_writer.data, f)
        os.replace(tmp, yaml_writer.file)

    return redirect(request.META.get("HTTP_REFERER", "/"))

def get_objects_yaml(request):
    #gets individual values from objects yaml
    course = request.GET.get("course")
    mode = request.GET.get("mode")
    key = request.GET.get("key")

    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}
    text = data.get(course, {}).get(mode, {}).get(key, "")
    return HttpResponse(str(text), content_type="text/plain")
    
OBJECTS_YAML_FILE = Path(settings.BASE_DIR).parent.parent / "objects.yaml"
def send_objects_yaml(request):
    #sends the portion of objects.yaml that matches specific course
    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}
        course = data.get("course")
        filtered = {
            "course": course,
            course: data[course],
        }
        return JsonResponse(filtered)

def make_default(request):
    file_name = "default"
    copy_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../objects_yaml_COPIES", file_name + ".yaml"))

    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}
    tmp = copy_file + ".tmp"

    with open(tmp, "w") as f:
        yaml.dump(data, f)
    
    os.replace(tmp, copy_file)
    return redirect(request.META.get("HTTP_REFERER", "/"))



def copy_yaml(request):
    #creates a copy of the current yaml file and puts into objects_yaml_COPIES folder
    file_name = str(request.GET.get("title"))
    copy_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../objects_yaml_COPIES", file_name + ".yaml"))
    offset = 0
    while(os.path.isfile(copy_file)):
        offset += 1
        copy_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../objects_yaml_COPIES", file_name + str(offset) + ".yaml"))
    
    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}
    tmp = copy_file + ".tmp"

    with open(tmp, "w") as f:
        yaml.dump(data, f)
    
    os.replace(tmp, copy_file)
    return redirect(request.META.get("HTTP_REFERER", "/"))

def edit_mode_list(request):
    #edit mode list page render
    global color_mode 
    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}

    courses = [
        key for key, value in data.items()
        if isinstance(value, dict)
        and any(isinstance(v, dict) for v in value.values())
    ]
    current_course = data.get("course")
    use_modes = [
            key for key, value in data[current_course].items()
            if isinstance(value, dict)
    ]
    return render(request, "edit_mode_list.html", {"color_mode": color_mode, "courses":courses, "use_modes": use_modes})

def send_mode_list(request):
    #sends the mode list from objects.yaml
    course = request.GET.get("course")
    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}
        data = data.get(course)
    mode_list = data.get("mode_list")
    filtered = {
        "course": course, "mode_list": mode_list,
    }
    stream = StringIO()
    yaml.dump(filtered, stream)
    return HttpResponse(stream.getvalue(),content_type="text/yaml")

def add_mode(request):
    #add mode to mode list
    global yaml_writer
    mode = request.GET.get("mode")
    course = request.GET.get("course")

    with yaml_writer.lock:

        if yaml_writer.data[course]["mode_list"]=="":
            yaml_writer.data[course]["mode_list"] =  mode
        else:
            yaml_writer.data[course]["mode_list"] = yaml_writer.data[course]["mode_list"] + ", " + mode
        tmp = yaml_writer.file + ".tmp"
        
        with open(tmp, "w") as f:
            yaml.dump(yaml_writer.data, f)
        os.replace(tmp, yaml_writer.file)

    return redirect(request.META.get("HTTP_REFERER", "/"))

def reset_mode_list(request):
    #resets mode list to be empty
     global yaml_writer
     course = request.GET.get("course")
     with yaml_writer.lock:

        yaml_writer.data[course]["mode_list"] = ""

        tmp = yaml_writer.file + ".tmp"
        with open(tmp, "w") as f:
            yaml.dump(yaml_writer.data, f)
        os.replace(tmp, yaml_writer.file)

     return redirect(request.META.get("HTTP_REFERER", "/"))

def pid_tuning(request):
    #pid tuning page render
    global color_mode
    return render(request, "pid_tuning.html", {"color_mode": color_mode})

def get_pid(request):
    #sends the desired pid from objects.yaml
    pid_y = request.GET.get("y")   
    pid_x = request.GET.get("x")

    column = {"x": 0, "y": 1, "z": 2, "yaw": 3, "pitch": 4, "roll": 5}

    with open(OBJECTS_YAML_FILE, "r") as f:
        data = yaml.load(f) or {}
        text = str(data.get("pid")[pid_y][column[pid_x]])
      
    return HttpResponse(text, content_type="text/plain")

def set_pid(request):
    #sets pid with given value and xy value
    pid_y = request.GET.get("y") 

    pid_x = request.GET.get("x")
   
    val = float(request.GET.get("val"))

    column = {"x": 0, "y": 1, "z": 2, "yaw": 3, "pitch": 4, "roll": 5}

    with yaml_writer.lock:

        yaml_writer.data["pid"][pid_y][column[pid_x]] = val

        tmp = yaml_writer.file + ".tmp"
        with open(tmp, "w") as f:
            yaml.dump(yaml_writer.data, f)
        os.replace(tmp, yaml_writer.file)

    return redirect(request.META.get("HTTP_REFERER", "/"))

