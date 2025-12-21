from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
import os, subprocess, sys
from pathlib import Path
import socket
from modules.sensors.a50_dvl.dvl import UDP_IP, UDP_PORT

shared_memory_object = None

def DVLreset(request):
        serv_addr = (UDP_IP, UDP_PORT)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(serv_addr)
            json_command = {"command": "reset_dead_reckoning"}
            sock.send(json.dumps(json_command).encode())
            sock.close()
        except Exception as e:
            print("Failed to reset dead reckoning:", e)
        return HttpResponse("reset complete")


def recieveMemory(memory=None):
    #if called with parameter, reassigns memory object. if called with no parameter, returns the existing object
    global shared_memory_object
    if memory is None:
        return shared_memory_object
    shared_memory_object = memory

def index(request):
    #homepage render
    return render(request, 'index.html')

def launch(request):
    #runs launch.py
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "launch.py"
    process = subprocess.Popen(
             [sys.executable, "-u", str(script)],
             cwd = str(repo_root)
    )
    return render(request, 'index.html')

def hard_kill(request):
    #runs stop alias
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "hard_kill.sh"
    process = subprocess.Popen(
             ["sh", str(script)],
             cwd = str(repo_root)
    )
    return render(request, 'index.html')

def soft_kill(request):
    #runs soft stop (from launch.py)
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "soft_kill.py"
    process = subprocess.Popen(
             [sys.executable, "-u", str(script)],
             cwd = str(repo_root)
    )
    return render(request, 'index.html')

def start_button(request):
    #runs start_button.py
    repo_root = Path(settings.BASE_DIR).parents[1]
    script = repo_root / "start_button.py"
    process = subprocess.Popen(
             [sys.executable, "-u", str(script)],
             cwd = str(repo_root)
    )
    return render(request, 'index.html')

def view_telemetry(request): 
    #telemetry page render
    return render(request, "telemetry.html")

TEST_FILE = os.path.join(settings.BASE_DIR, "testVals.json")
def test_telemetry(request):
    #function to assist writing fake telemetry data into JSON file
    with open(TEST_FILE, "r") as f:
        return JsonResponse(json.load(f))

SHARED_MEMORY_FILE = os.path.join(settings.BASE_DIR, "telemetry.json")
def get_telemetry(request):
    #Writes shared memory into a json file
    with open(SHARED_MEMORY_FILE, "r") as f:
        return JsonResponse(json.load(f))

