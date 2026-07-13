from modules.vision.vision_model_main import camera, yolo

cam   = camera("webcam")               # laptop/dev webcam, no undistortion
# cam = camera("downfacing")           # the sub's real calibrated camera
# cam = camera("zed")

# imgsz=320 (down from the yolo() default of 640) - the downcam runs off a
# lower-tier ZED Box Mini with no GPU, so CPU inference time scales with
# pixel count. Trades some accuracy for a real speedup; raise it back toward
# 640 if detections start getting missed/misboxed at this size.
model = yolo("models/best.pt", imgsz=320)

while True:
    detections = model.infer(cam, headless=False, verbose=True)