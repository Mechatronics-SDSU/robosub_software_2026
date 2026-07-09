from modules.vision.vision_model_api import camera, yolo

cam   = camera("downfacing")           # or "zed"
model = yolo("models/best.pt")

while True:
    detections = model.infer(cam, headless=False, verbose=True)