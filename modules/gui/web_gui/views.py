from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
import os

shared_memory_object = None


def DVLreset(request):
        global shared_memory_object
        shared_memory_object.dvl_x.value = 0
        shared_memory_object.dvl_y.value = 0
        shared_memory_object.dvl_z.value = 0
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

