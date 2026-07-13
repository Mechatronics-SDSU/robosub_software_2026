from api import camera, yolo
from circles import detect_circles

cam = camera("downfacing")
model = yolo("yolov8n.pt", conf=0.25)  # auto-downloads if not cached

active_classes = [0, 1]

for _ in range(10):
    detections = model.infer(cam, headless=False, verbose=True, classes=active_classes)

active_classes = [5, 6, 7, 8]

for _ in range(10):
    detections = model.infer(cam, headless=False, verbose=True, classes=active_classes)