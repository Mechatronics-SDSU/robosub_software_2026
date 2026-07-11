"""
CLI tester for ModemComms over real M16 hardware.

Usage examples:

  # Sub A: send a 2-byte message
  python -m modules.modem.modem_comms_tester send --port COM5 --message "Hi"

  # Sub B: loop, printing every message received
  python -m modules.modem.modem_comms_tester listen --port COM7
"""

import argparse
import logging
import sys

from modules.modem.modem_comms import ModemComms

# The shared Logger class defaults to DEBUG, which floods this CLI with a
# "Returning None" line on every idle read_packet() poll. Quiet it down to
# INFO for interactive use; nothing below INFO is lost from the log file
# either since it's the same "default" logger everywhere.
logging.getLogger("default").setLevel(logging.INFO)


def cmd_send(args, comms: ModemComms) -> bool:
    modem = comms.open_modem(args.port, channel=args.channel, power_level=args.level, baudrate=args.baudrate)
    try:
        print(f"[send] sending {args.message!r}...")
        written = modem.send_two_bytes(args.message)
        ok = written == 2
        print(f"[send] {'SUCCEEDED' if ok else 'FAILED'} (wrote {written} bytes)")
        return ok
    finally:
        modem.close()


def cmd_listen(args, comms: ModemComms) -> bool:
    modem = comms.open_modem(args.port, channel=args.channel, power_level=args.level, baudrate=args.baudrate)
    print("[listen] waiting for messages, exit with ctrl+c")
    try:
        while True:
            packet = modem.read_packet()
            if packet is not None:
                print(f"[listen] received: {packet.decode('ISO-8859-1')!r}")
    except KeyboardInterrupt:
        return True
    finally:
        modem.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual/hardware tester for ModemComms")
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--baudrate", type=int, default=9600)

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_send = subparsers.add_parser("send", help="send a 2-byte message")
    p_send.add_argument("--port", required=True)
    p_send.add_argument("--message", required=True, help="exactly 2 characters to send")
    p_send.set_defaults(func=cmd_send)

    p_listen = subparsers.add_parser("listen", help="loop, printing every message received")
    p_listen.add_argument("--port", required=True)
    p_listen.set_defaults(func=cmd_listen)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "send" and len(args.message) != 2:
        parser.error(f"--message must be exactly 2 characters, got {len(args.message)}")

    comms = ModemComms()
    ok = args.func(args, comms)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
