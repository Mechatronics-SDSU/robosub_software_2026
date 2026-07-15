"""
Send/receive helper for the M16 modem. Thin wrapper around modem_driver.M16
that matches the vendor reference driver's transparent-mode string protocol:
messages are sent and received as plain text (see sending_examples.py /
receive_example.py for the reference usage this mirrors).

Also provides a small binary frame protocol used by Modem_FSM for the
sub-to-sub data/ack handshake:

    5-bit code = frame_number(1) | frame_type(1, 0=DATA/1=ACK) | color_flag(1) | task_code(2)

The code is repeated 3x (15 bits) plus 1 padding bit = 2 bytes on the wire.
Frames are exactly 2 bytes -- the modem's transparent-mode transmission
only reliably carries 2 bytes per burst (confirmed on real hardware: a
3rd byte tacked onto one write was consistently dropped), matching why the
vendor driver only exposes a two-byte send primitive in the first place.

A stray byte from the modem itself (e.g. a "transmitting" status echo) can
land ahead of a real frame and misalign a naive "always read offset 0"
decode. Since we can't spend a byte on a sync marker, _extract_frame
instead tries every possible starting offset in the accumulated buffer and
accepts the first one that majority-votes successfully. On receive, the 3
repeated copies are majority-voted (at least 2 of 3 must match exactly) to
tolerate single-copy bit corruption; the padding bit isn't checked.
Reliability against a dropped frame comes from sending each frame several
times back-to-back (see send_frame_redundant, default 4 copies) rather
than a conditional retry, so there's no attempt-counter state to track --
the stray byte tends to only contaminate the first capture window, so
later copies get more chances to arrive clean.
"""

from modules.logger.logger import Logger
from modules.modem.modem_driver import M16
import threading

FRAME_TYPE_DATA = 0
FRAME_TYPE_ACK = 1

# Config commands (set_channel/set_level/set_diagnostic_mode/reset_diagnostic_mode/
# toggle_mode/get_report) send plain ASCII command/digit characters that can leak
# onto the acoustic channel and get picked up by a listener. A 2-byte payload made
# up entirely of these characters is treated as setup noise, not a real frame -- see
# _decode_payload. None of our own real frame encodings ever land entirely within
# this character set (verified: all 32 possible 5-bit codes produce byte pairs
# outside it).
_CHANNEL_CHARS = {{10: "a", 11: "b", 12: "c"}.get(c, str(c)) for c in M16.CHANNELS}
_LEVEL_CHARS = {str(l) for l in M16.LEVELS}
_COMMAND_CHARS = {"c", "l", "t", "d", "m", "r"}
MODEM_CONFIG_CHARS = _COMMAND_CHARS | _CHANNEL_CHARS | _LEVEL_CHARS


class ModemComms:
    def __init__(self):
        self.logger = Logger()
        self.process_name = "ModemComms"

        # background listener state (plain-text)
        self._listener_thread = None
        self._listening = False
        self._latest_message = None
        self._lock = threading.Lock()

        # background listener state (binary frame protocol)
        self._frame_listener_thread = None
        self._frame_listening = False
        self._latest_frame = None
        self._frame_lock = threading.Lock()

    def open_modem(
        self,
        port: str,
        channel: int = 1,
        power_level: int = 4,
        baudrate: int = 9600,
        diagnostic: bool = False,
    ) -> M16:
        """
        Open and fully configure the modem.
        """
        return M16(port, baudrate=baudrate, channel=channel, level=power_level, diagnostic=diagnostic)

    def send_message(self, modem: M16, message: str) -> bool:
        """
        Send a text message using the driver's send_msg (2-character chunks).
        """
        sent_chars = modem.send_msg(message)

        if not sent_chars:
            self.logger.warning(f"Failed to send message: {message!r}")
            return False

        self.logger.info(f"Sent message: {message!r}")
        return True

    def _listen_loop(self, modem: M16) -> None:
        """
        Background loop that keeps reading packets and stores the newest one.
        """
        while self._listening:
            packet = modem.read_packet()
            if packet is not None:
                decoded = packet.decode("ISO-8859-1")
                with self._lock:
                    self._latest_message = decoded
                self.logger.info(f"Received message: {decoded!r}")

    def start_listener(self, modem: M16) -> None:
        """
        Start a background thread that keeps listening for incoming messages.
        """
        if self._listener_thread is not None:
            return

        self._listening = True
        self._listener_thread = threading.Thread(target=self._listen_loop, args=(modem,), daemon=True)
        self._listener_thread.start()
        self.logger.info("Modem listener started")

    def stop_listener(self) -> None:
        """
        Stop the background listener thread, if one is running.
        """
        if self._listener_thread is None:
            return

        self._listening = False
        self._listener_thread.join(timeout=2.0)
        self._listener_thread = None
        self.logger.info("Modem listener stopped")

    def get_latest_message(self):
        """
        Return the most recently received message, or None if nothing new has arrived.
        """
        with self._lock:
            latest = self._latest_message
            self._latest_message = None
        return latest

    # -- binary frame protocol (used by Modem_FSM) --------------------------

    def pack_frame(self, frame_number: int, frame_type: int, color_flag: int, task_code: int) -> bytes:
        """
        Pack the 5-bit frame fields into a 2-byte wire frame: the 5-bit code
        repeated 3 times (15 bits) plus 1 padding bit. Exactly 2 bytes --
        see the module docstring for why a 3rd (sync marker) byte isn't an
        option on this hardware.
        """
        if frame_number not in (0, 1):
            raise ValueError("frame_number must be 0 or 1")
        if frame_type not in (FRAME_TYPE_DATA, FRAME_TYPE_ACK):
            raise ValueError("frame_type must be 0 (DATA) or 1 (ACK)")
        if color_flag not in (0, 1):
            raise ValueError("color_flag must be 0 or 1")
        if not 0 <= task_code <= 0b11:
            raise ValueError("task_code must be between 0 and 3")

        code = (frame_number << 4) | (frame_type << 3) | (color_flag << 2) | task_code
        packed = (code << 11) | (code << 6) | (code << 1)  # trailing bit is just padding
        return packed.to_bytes(2, byteorder="big")

    def _majority_vote(self, chunk1: str, chunk2: str, chunk3: str):
        """
        Return the trusted 5-bit chunk when at least two of the three match exactly.
        """
        if chunk1 == chunk2 or chunk1 == chunk3:
            return chunk1
        if chunk2 == chunk3:
            return chunk2
        return None

    def _looks_like_config_noise(self, payload: bytes) -> bool:
        """
        True if both payload bytes are printable ASCII characters from the
        modem's own config-command charset (see MODEM_CONFIG_CHARS). A
        handful of these combinations can coincidentally pass majority vote
        and decode as a fake valid frame, so they're filtered out before
        decoding is even attempted.
        """
        try:
            chars = payload.decode("ascii")
        except UnicodeDecodeError:
            return False
        return all(c in MODEM_CONFIG_CHARS for c in chars)

    def _decode_payload(self, payload: bytes):
        """
        Majority-vote decode a 2-byte payload (the bytes immediately after
        a sync marker) into its frame fields. Returns None if it looks like
        modem config/setup noise or the 3 repeated copies don't agree.
        """
        if self._looks_like_config_noise(payload):
            self.logger.debug(f"Ignoring likely modem-config noise: payload={payload!r}")
            return None

        binary_string = "".join(f"{byte:08b}" for byte in payload)
        bits = binary_string[:15]  # trailing padding bit is ignored, not checked
        chunk1, chunk2, chunk3 = bits[0:5], bits[5:10], bits[10:15]

        trusted = self._majority_vote(chunk1, chunk2, chunk3)
        if trusted is None:
            self.logger.warning(
                f"Majority vote failed: chunk1={chunk1} chunk2={chunk2} chunk3={chunk3} payload={payload!r}"
            )
            return None

        code = int(trusted, 2)
        return {
            "frame_number": (code >> 4) & 1,
            "frame_type": (code >> 3) & 1,
            "color_flag": (code >> 2) & 1,
            "task_code": code & 0b11,
        }

    def _extract_frame(self, buffer: bytes):
        """
        Try to decode one 2-byte frame from buffer, trying every possible
        starting offset (not just offset 0) and accepting the first one
        that majority-votes successfully. This is how misalignment from a
        stray leading byte gets recovered from without spending a 3rd byte
        on a sync marker (the modem can't reliably transmit more than 2
        bytes per burst -- see the module docstring).

        Returns (frame_or_None, remaining_buffer):
          - a decode succeeds at some offset: return the frame, and
            whatever's left in buffer after the consumed 2 bytes
          - nothing decodes at any offset: keep only the last byte (in
            case it's the start of a frame whose second byte hasn't
            arrived yet), discarding everything before it
        """
        for offset in range(max(len(buffer) - 1, 0)):
            frame = self._decode_payload(buffer[offset : offset + 2])
            if frame is not None:
                return frame, buffer[offset + 2 :]

        return None, buffer[-1:]

    def send_frame(self, modem: M16, frame_number: int, frame_type: int, color_flag: int, task_code: int) -> bool:
        """
        Pack and send one frame.
        """
        data = self.pack_frame(frame_number, frame_type, color_flag, task_code)
        written = modem.send_raw_bytes(data)

        if written != len(data):
            self.logger.warning(f"Failed to send frame: wrote {written} bytes")
            return False

        self.logger.info(
            f"Sent frame: frame_number={frame_number} frame_type={frame_type} "
            f"color_flag={color_flag} task_code={task_code}"
        )
        return True

    def send_frame_redundant(self, modem: M16, frame_number: int, frame_type: int, color_flag: int, task_code: int, copies: int = 4) -> bool:
        """
        Send the same frame `copies` times back-to-back for reliability,
        instead of conditionally retrying only on detected failure. A stray
        byte the modem echoes once (e.g. leftover from its own setup
        commands) tends to only contaminate the first capture window on the
        receiving end, so extra copies beyond the first give later, clean
        copies more chances to get through uncontaminated.
        """
        results = [self.send_frame(modem, frame_number, frame_type, color_flag, task_code) for _ in range(copies)]

        # The modem can emit a stray status byte (e.g. a "transmitting" ack)
        # after keying up to send. Clear it before the caller starts
        # listening for a reply, or it misaligns the next 2-byte frame read.
        modem.clear_buffers()

        return all(results)

    def _frame_listen_loop(self, modem: M16, expected_frame_type) -> None:
        """
        Background loop that keeps reading and decoding frames, storing the
        newest one whose frame_type matches (if a filter was given). Bytes
        are accumulated across calls (see _extract_frame) since a 3-byte
        frame isn't guaranteed to fully arrive within read_packet()'s own
        ~2 second window -- treating each call's result as self-contained
        would lose a frame split across two calls.
        """
        buffer = b""
        while self._frame_listening:
            try:
                raw = modem.read_packet()
            except Exception as e:
                # e.g. the serial port got closed out from under this thread
                # because stop_frame_listener()'s join() timed out before this
                # loop noticed _frame_listening went False -- stop quietly
                # instead of crashing with an unhandled thread exception.
                self.logger.debug(f"Frame listener stopping due to read error: {e}")
                return

            if raw:
                buffer += raw

            frame, buffer = self._extract_frame(buffer)
            if frame is None:
                continue

            if expected_frame_type is not None and frame["frame_type"] != expected_frame_type:
                self.logger.debug(f"Ignoring frame with unexpected frame_type: {frame}")
                continue

            with self._frame_lock:
                self._latest_frame = frame
            self.logger.info(f"Received frame: {frame}")

    def start_frame_listener(self, modem: M16, expected_frame_type=None) -> None:
        """
        Start a background thread that keeps listening for incoming frames.
        expected_frame_type filters out frames of the wrong type (e.g. a
        stray DATA frame while waiting for an ACK).
        """
        if self._frame_listener_thread is not None:
            return

        self._frame_listening = True
        self._frame_listener_thread = threading.Thread(
            target=self._frame_listen_loop, args=(modem, expected_frame_type), daemon=True
        )
        self._frame_listener_thread.start()
        self.logger.info("Frame listener started")

    def stop_frame_listener(self) -> None:
        """
        Stop the background frame listener thread, if one is running. Blocks
        until the thread actually exits (read_packet's own internal window
        caps how long that can take) so the caller can safely close the
        modem right after this returns without racing the listener thread.
        """
        if self._frame_listener_thread is None:
            return

        self._frame_listening = False
        thread = self._frame_listener_thread
        thread.join(timeout=5.0)
        if thread.is_alive():
            self.logger.warning("Frame listener thread did not stop in time; closing the modem may race it")
        self._frame_listener_thread = None
        self.logger.info("Frame listener stopped")

    def get_latest_frame(self):
        """
        Return the most recently received frame dict, or None if nothing new has arrived.
        """
        with self._frame_lock:
            latest = self._latest_frame
            self._latest_frame = None
        return latest
