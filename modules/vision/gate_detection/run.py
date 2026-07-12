#!/usr/bin/env python3
"""Run gate detection live from this directory.

    python3 run.py                     # live ZED Mini, print gate every frame
    python3 run.py --once              # single frame, then exit
    python3 run.py --detections        # print YOLO-format detections instead
    python3 run.py --svo clip.svo2     # replay a recording
    python3 run.py --record clip.svo2  # record while running live

Ctrl+C stops cleanly.
"""

import argparse
import asyncio
import json

from gate_detector import GateDetector


def parse_args():
    p = argparse.ArgumentParser(description="Live gate detection on the ZED Mini")
    p.add_argument("--svo", metavar="PATH", help="replay an .svo2 recording instead of the live camera")
    p.add_argument("--record", metavar="PATH", help="record the live session to an .svo2 file")
    p.add_argument("--once", action="store_true", help="process a single frame and exit")
    p.add_argument("--detections", action="store_true",
                   help="print get_detections() YOLO-format output instead of the gate dict")
    return p.parse_args()


def summarize(gate):
    """One line per frame: what we see and where to go."""
    parts = []
    for name in ("left", "right", "divider"):
        p = gate[name]
        if p:
            x, y, z = p["position"]
            parts.append(f"{name}=({x:+.2f},{y:+.2f},{z:.2f})m conf={p['confidence']:.2f}")
    mid = gate["gate_midpoint"]
    if mid:
        parts.append(f"midpoint=({mid[0]:+.2f},{mid[1]:+.2f},{mid[2]:.2f})m")
    parts.append(f"hint={gate['direction_hint']}")
    return "  ".join(parts)


async def main():
    args = parse_args()
    frames = 0
    async with GateDetector(svo_path=args.svo, record_path=args.record) as detector:
        while True:
            if args.detections:
                out = await detector.get_detections()
                print(json.dumps(out))
            else:
                gate = await detector.get_gate()
                if gate is None:  # SVO replay exhausted
                    print(f"end of recording after {frames} frames")
                    break
                print(summarize(gate))
            frames += 1
            if args.once:
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped")
