#!/usr/bin/env python3
"""
Standalone ZED camera troubleshooting script for the Jetson (or any Linux
box). Run this directly - it does NOT require the ZED to actually open, and
never crashes even if the ZED SDK isn't installed at all:

    python modules/vision/zed_troubleshoot.py

Runs, in order:
    1. lsusb                                    - is the ZED visible on USB at all?
    2. lsusb -t                                 - is it on the USB3 SuperSpeed tree (5000M) or only USB2 (12M/480M)?
    3. v4l2-ctl --list-devices                  - what video devices does the kernel see (sanity check
                                                   against other cameras, e.g. the exploreHD/downfacing camera)
    4. /usr/local/zed/tools/ZED_Diagnostic      - Stereolabs' own diagnostic tool, if installed (run headlessly
                                                   with a timeout; if it hangs waiting for a display, it's killed)
    5. /usr/local/zed/tools/ZED_Explorer        - reported as present/absent only, NOT executed (it's an
                                                   interactive GUI tool - run it yourself if you need it:
                                                   /usr/local/zed/tools/ZED_Explorer)
    6. The same SDK-level checks ZEDCamera itself runs on open failure
       (modules/vision/zed_diagnostics.py): pyzed import, SDK version,
       sl.Camera.get_device_list()

Then prints a single plain-English diagnosis at the end: ZED not connected at
all / only its HID interface is visible (USB3 link not up) / USB3 present but
inconclusive / looks OK at the USB level.

See modules/vision/zed_diagnostics.py's module docstring for why a ZED 2i
showing up ONLY as "2b03:f881 STEREOLABS ZED-2i HID INTERFACE" in `lsusb`
means the USB3 video/depth link specifically isn't up - not a code bug here.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.vision.zed_diagnostics import (  # noqa: E402
    ZED_DIAGNOSTIC_TOOL,
    ZED_EXPLORER_TOOL,
    run_lsusb,
    run_lsusb_tree,
    run_v4l2_list_devices,
    diagnose_zed,
)


def section(title: str) -> None:
    print()
    print(f"===== {title} =====")


def run_zed_diagnostic_tool(timeout: float = 15.0) -> None:
    if not os.path.isfile(ZED_DIAGNOSTIC_TOOL):
        print(f"(not found: {ZED_DIAGNOSTIC_TOOL})")
        return
    try:
        result = subprocess.run([ZED_DIAGNOSTIC_TOOL], capture_output=True, text=True, timeout=timeout)
        print(result.stdout)
        if result.stderr:
            print(f"[stderr] {result.stderr}")
    except subprocess.TimeoutExpired:
        print(f"({ZED_DIAGNOSTIC_TOOL} did not finish within {timeout}s - killed. "
              f"It may be waiting on interactive input or a display; try running it "
              f"manually in a real terminal if you need its full report.)")
    except Exception as e:
        print(f"({ZED_DIAGNOSTIC_TOOL} failed to run: {e})")


def report_zed_explorer() -> None:
    exists = os.path.isfile(ZED_EXPLORER_TOOL)
    print(f"{ZED_EXPLORER_TOOL} exists: {exists}")
    if exists:
        print("Not run automatically - it's an interactive GUI tool. Run it yourself if you "
              f"need a live preview: {ZED_EXPLORER_TOOL}")


def main() -> None:
    section("lsusb")
    print(run_lsusb())

    section("lsusb -t")
    print(run_lsusb_tree())

    section("v4l2-ctl --list-devices")
    print(run_v4l2_list_devices())

    section("ZED_Diagnostic")
    run_zed_diagnostic_tool()

    section("ZED_Explorer")
    report_zed_explorer()

    section("SDK-level diagnosis (same checks ZEDCamera runs on open failure)")
    diagnose_zed(emit=print)


if __name__ == "__main__":
    main()
