import pyzed.sl as sl

# --- Open camera ---
init_params = sl.InitParameters()
init_params.coordinate_units = sl.UNIT.METER          # nice: meters
init_params.coordinate_system = sl.COORDINATE_SYSTEM.RIGHT_HANDED_Y_UP
zed = sl.Camera()
assert zed.open(init_params) == sl.ERROR_CODE.SUCCESS

# --- Enable positional tracking (VIO uses the ZED 2i IMU automatically) ---
tracking_params = sl.PositionalTrackingParameters()
assert zed.enable_positional_tracking(tracking_params) == sl.ERROR_CODE.SUCCESS

runtime = sl.RuntimeParameters()
pose = sl.Pose()

while True:
    if zed.grab(runtime) == sl.ERROR_CODE.SUCCESS:
        state = zed.get_position(pose, sl.REFERENCE_FRAME.WORLD)  # or FRAME_CAMERA for odometry
        if state == sl.POSITIONAL_TRACKING_STATE.OK:
            t = sl.Translation()
            pose.get_translation(t)           # fills t
            tx, ty, tz = t.get()              # numpy-like array of [x,y,z]
            print(f"translation (world): {tx:.3f}, {ty:.3f}, {tz:.3f}")
        else:
            print("tracking:", state)         # SEARCHING / FPS_TOO_LOW / etc.
