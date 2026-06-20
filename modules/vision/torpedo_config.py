"""
Torpedo hardware and control config loader.

This file intentionally reads only environment/hardware/control values.
Course-specific target coordinates still belong in objects.yaml because those
change with the course layout, not the submarine hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_ENV_PATH = "~/robosub_software_2026/.env"


# Rectified image FOV values from Stereolabs' FOV table.
# Values are (horizontal_fov_deg, vertical_fov_deg).
# If you change camera resolution, update the env value or let this table pick
# the matching default.
RECTIFIED_FOV_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("ZED_2I", "HD2K"): (92.0, 61.0),
    ("ZED_2I", "HD1080"): (84.0, 54.0),
    ("ZED_2I", "HD720"): (101.0, 68.0),
    ("ZED_2I", "WVGA"): (103.0, 71.0),
    ("ZED_X_MINI", "HD1200"): (105.0, 78.0),
    ("ZED_X_MINI", "HD1080"): (105.0, 72.0),
    ("ZED_X_MINI", "SVGA"): (105.0, 78.0),
}


@dataclass(frozen=True)
class TorpedoConfig:
    """
    Values needed by torpedo vision-to-PID lineup.
    """

    sub_name: str
    camera_model: str
    camera_resolution: str
    camera_fov_x_deg: float
    camera_fov_y_deg: float
    vision_config_path: str

    target_label: str
    conf_threshold: float
    min_torpedo_distance: float
    max_torpedo_distance: float

    search_window_frames: int
    search_required_frames: int
    track_window_frames: int
    track_required_frames: int
    verify_window_frames: int
    verify_required_frames: int

    search_timeout: float
    movement_timeout: float
    camera_startup_delay: float
    pre_shoot_hold_sec: float
    post_shoot_wait_sec: float

    x_gain: float
    y_gain: float
    z_gain: float
    x_sign: float
    y_sign: float
    z_sign: float



def load_env_file(path: str) -> dict[str, str]:
    """
    Minimal .env reader.

    Supports:
        KEY=value
        KEY="value"
        KEY='value'

    Real environment variables are applied later and override this file.
    """

    values: dict[str, str] = {}
    path = os.path.expanduser(path)

    try:
        with open(path, "r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()

                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                values[key] = value

    except FileNotFoundError:
        pass

    return values



def load_torpedo_config(path: str = DEFAULT_ENV_PATH) -> TorpedoConfig:
    """
    Load torpedo config from .env.

    Sub-specific values are checked first. Example:
        CARACARA_CAMERA_FOV_X_DEG=84.0

    Shared values are used as fallback. Example:
        TORPEDO_CONF_THRESHOLD=0.70
    """

    env = load_env_file(path)
    env.update(os.environ)

    sub_name = _get_first_existing(
        env,
        ["SUB_NAME", "ROBO_SUB_NAME", "VEHICLE_NAME"],
        "",
    ).upper()

    if not sub_name:
        raise ValueError(
            "Missing SUB_NAME. Expected SUB_NAME=CARACARA or SUB_NAME=TORPICO."
        )

    default_camera = _default_camera_for_sub(sub_name)
    camera_model = str(
        _get_sub_value(env, sub_name, "CAMERA_MODEL", default_camera)
    ).upper()
    camera_resolution = str(
        _get_sub_value(env, sub_name, "CAMERA_RESOLUTION", "HD1080")
    ).upper()

    default_fov_x, default_fov_y = _default_fov(camera_model, camera_resolution)

    return TorpedoConfig(
        sub_name=sub_name,
        camera_model=camera_model,
        camera_resolution=camera_resolution,
        camera_fov_x_deg=_read_float(
            env,
            sub_name,
            "CAMERA_FOV_X_DEG",
            default_fov_x,
        ),
        camera_fov_y_deg=_read_float(
            env,
            sub_name,
            "CAMERA_FOV_Y_DEG",
            default_fov_y,
        ),
        vision_config_path=os.path.expanduser(
            _get_sub_value(
                env,
                sub_name,
                "VISION_CONFIG_PATH",
                "~/robosub_software_2026/modules/vision/config.yaml",
            )
        ),
        target_label=str(
            _get_sub_value(env, sub_name, "TORPEDO_TARGET_LABEL", "torpedo")
        ),
        conf_threshold=_read_float(
            env,
            sub_name,
            "TORPEDO_CONF_THRESHOLD",
            0.70,
        ),
        min_torpedo_distance=_read_float(
            env,
            sub_name,
            "TORPEDO_MIN_DISTANCE_M",
            0.5,
        ),
        max_torpedo_distance=_read_float(
            env,
            sub_name,
            "TORPEDO_MAX_DISTANCE_M",
            8.0,
        ),
        search_window_frames=_read_int(
            env,
            sub_name,
            "TORPEDO_SEARCH_WINDOW_FRAMES",
            30,
        ),
        search_required_frames=_read_int(
            env,
            sub_name,
            "TORPEDO_SEARCH_REQUIRED_FRAMES",
            10,
        ),
        track_window_frames=_read_int(
            env,
            sub_name,
            "TORPEDO_TRACK_WINDOW_FRAMES",
            15,
        ),
        track_required_frames=_read_int(
            env,
            sub_name,
            "TORPEDO_TRACK_REQUIRED_FRAMES",
            4,
        ),
        verify_window_frames=_read_int(
            env,
            sub_name,
            "TORPEDO_VERIFY_WINDOW_FRAMES",
            10,
        ),
        verify_required_frames=_read_int(
            env,
            sub_name,
            "TORPEDO_VERIFY_REQUIRED_FRAMES",
            6,
        ),
        search_timeout=_read_float(
            env,
            sub_name,
            "TORPEDO_SEARCH_TIMEOUT",
            30.0,
        ),
        movement_timeout=_read_float(
            env,
            sub_name,
            "TORPEDO_MOVEMENT_TIMEOUT",
            30.0,
        ),
        camera_startup_delay=_read_float(
            env,
            sub_name,
            "TORPEDO_CAMERA_STARTUP_DELAY",
            2.0,
        ),
        pre_shoot_hold_sec=_read_float(
            env,
            sub_name,
            "TORPEDO_PRE_SHOOT_HOLD_SEC",
            0.5,
        ),
        post_shoot_wait_sec=_read_float(
            env,
            sub_name,
            "TORPEDO_POST_SHOOT_WAIT_SEC",
            1.0,
        ),
        x_gain=_read_float(env, sub_name, "TORPEDO_X_GAIN", 1.0),
        y_gain=_read_float(env, sub_name, "TORPEDO_Y_GAIN", 1.0),
        z_gain=_read_float(env, sub_name, "TORPEDO_Z_GAIN", 1.0),
        x_sign=_read_float(env, sub_name, "TORPEDO_X_SIGN", 1.0),
        y_sign=_read_float(env, sub_name, "TORPEDO_Y_SIGN", 1.0),
        z_sign=_read_float(env, sub_name, "TORPEDO_Z_SIGN", 1.0),
    )



def _default_camera_for_sub(sub_name: str) -> str:
    if sub_name == "CARACARA":
        return "ZED_2I"

    if sub_name == "TORPICO":
        return "ZED_X_MINI"

    return "ZED_2I"



def _default_fov(camera_model: str, camera_resolution: str) -> tuple[float, float]:
    key = (camera_model.upper(), camera_resolution.upper())

    if key in RECTIFIED_FOV_TABLE:
        return RECTIFIED_FOV_TABLE[key]

    raise ValueError(
        "Missing camera FOV. Set "
        f"{camera_model}_{camera_resolution} in RECTIFIED_FOV_TABLE or add "
        "CAMERA_FOV_X_DEG and CAMERA_FOV_Y_DEG to .env."
    )



def _get_first_existing(env: dict[str, str], keys: list[str], default=None):
    for key in keys:
        if key in env:
            return env[key]

    return default



def _get_sub_value(env: dict[str, str], sub_name: str, key: str, default=None):
    sub_key = f"{sub_name}_{key}"

    if sub_key in env:
        return env[sub_key]

    return env.get(key, default)



def _read_int(env: dict[str, str], sub_name: str, key: str, default: int) -> int:
    value = _get_sub_value(env, sub_name, key, default)
    return int(str(value), 0)



def _read_float(env: dict[str, str], sub_name: str, key: str, default: float) -> float:
    value = _get_sub_value(env, sub_name, key, default)
    return float(value)
