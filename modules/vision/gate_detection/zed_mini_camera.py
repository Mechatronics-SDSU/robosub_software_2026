"""Thin wrapper around the ZED SDK, configured for the ZED Mini.

All pyzed calls live in this file. The detector and locator only ever see
numpy arrays, so swapping the ZED Mini for another depth camera means
touching only this file and config.yaml.

ZED Mini vs ZED 2i notes (the pyzed API itself is identical):
  - 63 mm baseline (vs 120 mm): minimum depth goes down to ~0.1 m, but
    depth noise grows faster with range -- expect usable pillar depth to
    ~6 m rather than ~8 m.
  - Supported resolutions: HD2K@15, HD1080@30, HD720@60, VGA@100.
  - pyzed is imported lazily so this module stays importable on machines
    without the ZED SDK.
"""

import numpy as np


class ZedMiniCamera:
    """Opens a live ZED Mini or replays an .svo2 recording.

    get_frame() returns (bgr_image, depth_m, point_cloud_xyz) or None when
    an SVO recording is exhausted. Arrays are views into SDK-owned memory
    and are only valid until the next get_frame() call.
    """

    def __init__(self, cam_cfg, svo_path=None, record_path=None):
        import pyzed.sl as sl
        self._sl = sl

        init = sl.InitParameters()
        init.coordinate_units = sl.UNIT.METER
        init.camera_resolution = getattr(sl.RESOLUTION, cam_cfg["resolution"])
        init.camera_fps = int(cam_cfg["fps"])
        init.depth_mode = getattr(sl.DEPTH_MODE, cam_cfg["depth_mode"])
        init.depth_minimum_distance = float(cam_cfg["depth_min_m"])
        init.depth_maximum_distance = float(cam_cfg["depth_max_m"])
        if svo_path:
            init.set_from_svo_file(svo_path)
            init.svo_real_time_mode = False  # process every frame

        self.cam = sl.Camera()
        status = self.cam.open(init)
        if status != sl.ERROR_CODE.SUCCESS:
            raise RuntimeError(f"Failed to open ZED Mini: {status}")

        if record_path:
            rec = sl.RecordingParameters(record_path, sl.SVO_COMPRESSION_MODE.H265)
            status = self.cam.enable_recording(rec)
            if status != sl.ERROR_CODE.SUCCESS:
                self.cam.close()
                raise RuntimeError(f"Failed to start SVO recording: {status}")

        info = self.cam.get_camera_information()
        left_cam = info.camera_configuration.calibration_parameters.left_cam
        self.fx = left_cam.fx
        self.fy = left_cam.fy
        self.model = str(info.camera_model)
        self.width = info.camera_configuration.resolution.width
        self.height = info.camera_configuration.resolution.height

        if svo_path is None and info.camera_model != sl.MODEL.ZED_M:
            print(f"[ZedMiniCamera] warning: expected a ZED Mini, "
                  f"found {self.model}; continuing with its calibration")

        self._runtime = sl.RuntimeParameters()
        self._img = sl.Mat()
        self._depth = sl.Mat()
        self._pc = sl.Mat()

    def get_frame(self):
        sl = self._sl
        err = self.cam.grab(self._runtime)
        if err == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
            return None
        if err != sl.ERROR_CODE.SUCCESS:
            raise RuntimeError(f"ZED grab failed: {err}")

        self.cam.retrieve_image(self._img, sl.VIEW.LEFT)
        self.cam.retrieve_measure(self._depth, sl.MEASURE.DEPTH)
        self.cam.retrieve_measure(self._pc, sl.MEASURE.XYZ)

        bgr = self._img.get_data()[:, :, :3]          # BGRA -> BGR
        depth = self._depth.get_data()                # float32, m; NaN = invalid
        pc = self._pc.get_data()[:, :, :3]            # float32 XYZ, m
        return bgr, depth, pc

    def close(self):
        self.cam.close()
