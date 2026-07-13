from modules.vision.vision_model_main import camera, yolo

cam   = camera("webcam")               # laptop/dev webcam, no undistortion
# cam = camera("downfacing")           # the sub's real calibrated camera
# cam = camera("zed")

model = yolo("models/best.pt", imgsz=640)

while True:
    detections = model.infer(cam, headless=False, verbose=True)