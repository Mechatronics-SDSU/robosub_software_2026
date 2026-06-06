"""
Reusable two-byte handshake helper for the M16 modem.
"""

from modules.logger.logger import Logger

from time import sleep, monotonic
from modem_driver import M16


class ModemComms:
    def __init__(self):
        self.logger = Logger()
        self.process_name = "ModemComms"

    def encode_message(self, code: int) -> bytes:
        """
        Encode one 5-bit code into exactly two bytes.
        """
        if not 0 <= code <= 0b11111:
            raise ValueError("code must be between 0 and 31")

        packed = (code << 11) | (code << 6) | (code << 1) | 1
        return packed.to_bytes(2, byteorder="big")

    def majority_vote(self, chunk1: str, chunk2: str, chunk3: str):
        """
        Return the trusted 5-bit chunk when at least two chunks match.
        """
        if chunk1 == chunk2 or chunk1 == chunk3:
            return chunk1
        if chunk2 == chunk3:
            return chunk2
        return None

    def decode_message(self, raw):
        """
        Decode two modem bytes back into the original 5-bit code.
        """
        if raw is None or len(raw) != 2:
            self.logger.warning(f"Invalid raw message: expected 2 bytes, got {raw!r}")
            return None

        binary_string = "".join(f"{byte:08b}" for byte in raw)

        if binary_string[-1] != "1":
            self.logger.warning(f"Invalid message bit: {binary_string}")
            return None

        payload = binary_string[:-1]
        chunk1 = payload[0:5]
        chunk2 = payload[5:10]
        chunk3 = payload[10:15]

        trusted_chunk = self.majority_vote(chunk1, chunk2, chunk3)
        if trusted_chunk is None:
            self.logger.warning(
                f"Majority vote failed: chunk1={chunk1} chunk2={chunk2} chunk3={chunk3} raw={raw!r}"
            )
            return None

        return int(trusted_chunk, 2)

    def open_modem(
        self,
        port: str,
        channel: int = 1,
        power_level: int = 1,
        baudrate: int = 9600,
    ) -> M16:
        """
        Open and fully configure the modem before the handshake phase starts.
        """
        return M16(
            port,
            baudrate=baudrate,
            channel=channel,
            level=power_level,
            diagnostic=False,
        )

    def send_message(self, modem: M16, code: int) -> bool:
        """
        Encode and send one 2-byte message using the driver.
        """
        message = self.encode_message(code)

        self.logger.debug(f"DEBUG: sending raw bytes {message!r}")
        bytes_written = modem.send_two_bytes(message)
        self.logger.debug(f"DEBUG: bytes_written = {bytes_written}")

        if bytes_written != 2:
            self.logger.warning(f"Expected to send 2 bytes, but sent {bytes_written}")
            return False

        self.logger.info(f"Sent message: code={code} binary={int(f'{code:05b}')}")
        return True

    def wait_for_message(self, modem: M16, timeout: float = 30.0):
        """
        Wait for one valid 2-byte message using the driver's read_two_bytes function.
        """
        raw = modem.read_two_bytes(timeout=timeout)
        decoded = self.decode_message(raw)

        if decoded is None:
            self.logger.warning("No valid message received")
            return None

        self.logger.info(f"Received message: code={decoded} binary={f'{decoded:05b}'}")
        return decoded

    def listen_and_reply_with_modem(self, modem: M16, reply: int, timeout: float = 30.0) -> bool:
        """
        Use an already-configured modem to listen, then reply.
        """
        modem.clear_buffers()

        received = self.wait_for_message(modem, timeout=timeout)
        if received is None:
            return False

        self.logger.info(f"Replying to received message: {received} binary={f'{received:05b}'}")
        return self.send_message(modem, reply)

    def initiate_handshake_with_modem(
        self,
        modem: M16,
        message: int,
        expected_reply=None,
        reply_timeout: float = 30.0,
    ) -> bool:
        """
        Use an already-configured modem to send first, then wait for the reply.
        """
        modem.clear_buffers()

        if not self.send_message(modem, message):
            return False

        received = self.wait_for_message(modem, timeout=reply_timeout)
        if received is None:
            return False

        if expected_reply is not None and received != expected_reply:
            self.logger.warning(
                f"Expected reply {expected_reply} binary={expected_reply:05b}, but got {received} binary={received:05b}"
            )
            return False

        self.logger.info("Handshake successful")
        return True

    def listen_and_reply(
        self,
        port: str,
        reply: int,
        channel: int = 1,
        power_level: int = 1,
        baudrate: int = 9600,
        timeout: float = 30.0,
    ) -> bool:
        """
        Open/configure modem, listen for a message, and reply.
        """
        modem = self.open_modem(port, channel=channel, power_level=power_level, baudrate=baudrate)
        try:
            return self.listen_and_reply_with_modem(modem, reply=reply, timeout=timeout)
        finally:
            modem.close()

    def initiate_handshake(
        self,
        port: str,
        message: int,
        expected_reply=None,
        channel: int = 1,
        power_level: int = 1,
        baudrate: int = 9600,
        reply_timeout: float = 30.0,
        startup_delay: float = 0.0,
    ) -> bool:
        modem = M16(port, baudrate=baudrate, channel=channel, level=power_level)

        try:
            if startup_delay > 0:
                self.logger.info(f"Waiting {startup_delay} seconds before sending")
                sleep(startup_delay)

            modem.clear_buffers()

            if not self.send_message(modem, message):
                return False

            received = self.wait_for_message(modem, timeout=reply_timeout)
            if received is None:
                return False

            if expected_reply is not None and received != expected_reply:
                self.logger.warning(
                    f"Expected reply {expected_reply} binary={expected_reply:05b}, "
                    f"but got {received} binary={received:05b}"
                )
                return False

            self.logger.info("Handshake successful")
            return True

        finally:
            modem.close()