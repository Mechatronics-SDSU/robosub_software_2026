"""
ZED camera diagnostics - shared by ZEDCamera's open-failure path (in
modules/vision/vision_model_main.py) and the standalone
modules/vision/zed_troubleshoot.py script.

WHY THIS EXISTS:
A ZED 2i is a composite USB device with (at least) two logical interfaces:
  1. A small, low-bandwidth HID interface (buttons/LEDs/basic control) -
     this can enumerate over USB 2 (480M) even when nothing else works.
  2. The actual video/depth stream, which REQUIRES a working USB 3
     SuperSpeed link (usually shown as 5000M in `lsusb -t`).

If `lsusb` only shows "2b03:f881 STEREOLABS ZED-2i HID INTERFACE" and
`lsusb -t` shows no 5000M device, that means: the camera is powered and
partially recognized (enough for the tiny HID channel), but its main
USB3 video/depth interface never linked up. The ZED SDK then has nothing
to open - this is a physical/electrical USB3 connection problem (cable,
port, hub bandwidth/power), not a bug in this codebase's camera-opening
code. The diagnostics below exist to make that distinction obvious instead
of just re-printing the SDK's generic "CAMERA NOT DETECTED" error.
"""
import os
import subprocess

STEREOLABS_VENDOR_ID = "2b03"
ZED_INSTALL_DIR = "/usr/local/zed"
ZED_DIAGNOSTIC_TOOL = "/usr/local/zed/tools/ZED_Diagnostic"
ZED_EXPLORER_TOOL = "/usr/local/zed/tools/ZED_Explorer"


def check_zed_install_dir() -> bool:
    """Whether the ZED SDK appears to be installed at all."""
    return os.path.isdir(ZED_INSTALL_DIR)


def check_pyzed_import() -> tuple:
    """Returns (ok, error_message_or_None)."""
    try:
        import pyzed.sl  # noqa: F401
        return True, None
    except Exception as e:
        return False, str(e)


def get_sdk_version():
    """Returns the ZED SDK version string, or None if unavailable."""
    try:
        import pyzed.sl as sl
        return sl.Camera.get_sdk_version()
    except Exception:
        return None


def get_zed_device_list():
    """
    Returns the ZED SDK's own camera enumeration (a list of
    sl.DeviceProperties), or None if the SDK call itself failed. This asks
    the SDK "what ZED cameras can you see" independent of actually opening
    one - an empty list here means the SDK itself sees zero cameras, which
    is the clearest possible signal before even trying open().
    """
    try:
        import pyzed.sl as sl
        return sl.Camera.get_device_list()
    except Exception:
        return None


def run_command(args: list, timeout: float = 5.0) -> str:
    """Runs a command and returns its stdout, or a descriptive error string
    (never raises) - used for all the shell-out diagnostics below."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.stdout + result.stderr
    except FileNotFoundError:
        return f"({args[0]} not found on this system)"
    except subprocess.TimeoutExpired:
        return f"({' '.join(args)} timed out after {timeout}s)"
    except Exception as e:
        return f"({' '.join(args)} failed: {e})"


def run_lsusb() -> str:
    return run_command(["lsusb"])


def run_lsusb_tree() -> str:
    return run_command(["lsusb", "-t"])


def run_v4l2_list_devices() -> str:
    return run_command(["v4l2-ctl", "--list-devices"])


def find_stereolabs_usb_lines(lsusb_output: str) -> list:
    """Every line in `lsusb` output mentioning the Stereolabs vendor ID."""
    return [line for line in lsusb_output.splitlines() if STEREOLABS_VENDOR_ID in line.lower()]


def usb3_superspeed_present(lsusb_tree_output: str):
    """
    Heuristic, system-wide (not ZED-specific): does ANY 5000M (USB3
    SuperSpeed) device show up in `lsusb -t` at all? `lsusb -t` doesn't
    cleanly attribute a given speed line to a specific vendor ID without
    extra /sys parsing, so this can't prove the ZED itself is on USB3 - but
    if NO 5000M device exists anywhere on the system, that's a strong signal
    the ZED's link specifically isn't up either. Returns None if lsusb -t
    itself couldn't be run.
    """
    if lsusb_tree_output.startswith("("):
        return None
    return "5000M" in lsusb_tree_output


def classify_zed_usb_state(stereolabs_lines: list, usb3_present) -> str:
    """
    Returns one of: "not_connected", "hid_only", "usb3_present_unclear",
    "likely_ok" - the actual diagnosis this whole module exists to produce.
    """
    if not stereolabs_lines:
        return "not_connected"

    all_hid_only = all("hid" in line.lower() for line in stereolabs_lines)
    any_non_hid = any("hid" not in line.lower() for line in stereolabs_lines)

    if all_hid_only and not any_non_hid:
        return "hid_only"
    if usb3_present:
        return "likely_ok"
    return "usb3_present_unclear"


def diagnose_zed(emit=print) -> dict:
    """
    Runs the full diagnostic sweep. `emit(message)` is called once per line
    of human-readable output (defaults to print; pass a Logger-like
    `.info`/`.warning`/`.error` wrapped into a single callable if you want
    this to go through modules/logger/logger.py instead). Returns a dict of
    the raw results for programmatic use (e.g. deciding whether to fall back
    to another camera).
    """
    results = {}

    results["zed_install_dir_exists"] = check_zed_install_dir()
    emit(f"[ZED DIAG] {ZED_INSTALL_DIR} exists: {results['zed_install_dir_exists']}")

    pyzed_ok, pyzed_err = check_pyzed_import()
    results["pyzed_import_ok"] = pyzed_ok
    results["pyzed_import_error"] = pyzed_err
    emit(f"[ZED DIAG] pyzed.sl imports: {pyzed_ok}" + (f" ({pyzed_err})" if not pyzed_ok else ""))

    results["sdk_version"] = get_sdk_version() if pyzed_ok else None
    emit(f"[ZED DIAG] ZED SDK version: {results['sdk_version'] or 'unknown'}")

    device_list = get_zed_device_list() if pyzed_ok else None
    results["device_list"] = device_list
    if device_list is None:
        emit("[ZED DIAG] sl.Camera.get_device_list() could not be called")
    elif len(device_list) == 0:
        emit("[ZED DIAG] sl.Camera.get_device_list() returned 0 cameras - the SDK itself sees no ZED camera")
    else:
        for d in device_list:
            emit(f"[ZED DIAG] SDK sees device: id={d.id} serial={d.serial_number} "
                 f"model={d.camera_model} state={d.camera_state}")

    lsusb_out = run_lsusb()
    stereolabs_lines = find_stereolabs_usb_lines(lsusb_out)
    results["stereolabs_usb_lines"] = stereolabs_lines
    if not stereolabs_lines:
        emit(f"[ZED DIAG] No USB device with vendor ID {STEREOLABS_VENDOR_ID} (Stereolabs) found in `lsusb` "
             f"- the ZED isn't visible to the OS at all right now (check power/cable)")
    else:
        for line in stereolabs_lines:
            emit(f"[ZED DIAG] lsusb: {line}")

    lsusb_tree_out = run_lsusb_tree()
    results["lsusb_tree_raw"] = lsusb_tree_out
    usb3_present = usb3_superspeed_present(lsusb_tree_out)
    results["usb3_superspeed_seen_anywhere"] = usb3_present

    state = classify_zed_usb_state(stereolabs_lines, usb3_present)
    results["diagnosis"] = state

    if state == "not_connected":
        emit("[ZED DIAG] DIAGNOSIS: ZED not detected on USB at all. Check the cable is fully seated and the "
             "camera has power (LED on the ZED body).")
    elif state == "hid_only":
        emit("[ZED DIAG] DIAGNOSIS: Only the ZED's HID interface is visible (2b03:f881 ... HID INTERFACE). "
             "A healthy ZED 2i should also enumerate on the USB 3 SuperSpeed tree (usually 5000M in "
             "`lsusb -t`), not only the USB 2 tree (12M/480M) this HID interface is showing up on. This "
             "means the physical/electrical USB3 link isn't established - the device is powered and "
             "partially recognized, but the SDK has nothing to open. This is a cable/port/hub issue, not "
             "a bug in the camera-opening code.")
    elif state == "usb3_present_unclear":
        emit("[ZED DIAG] DIAGNOSIS: ZED is visible on USB, but no USB3 SuperSpeed (5000M) device was found "
             "anywhere on this system - consistent with the ZED's link not being up, though lsusb -t can't "
             "prove this is specifically the ZED without deeper /sys parsing.")
    elif state == "likely_ok":
        emit("[ZED DIAG] DIAGNOSIS: ZED is visible on USB and this system does have an active USB3 "
             "SuperSpeed link somewhere. If open() is still failing, the issue is more likely SDK/driver/"
             "permissions-related than a USB3 link problem - check the SDK version and device list above.")

    return results
