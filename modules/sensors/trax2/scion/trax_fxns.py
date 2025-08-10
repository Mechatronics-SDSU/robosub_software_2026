import struct
import logging
import serial
import time
from serial.tools import list_ports

"""
    Created by Ryan Sundermeyer
    https://github.com/rsunderr
    mechatronics@sundermeyer.com
"""

# wrapper class for trax-related functions
class TRAX:
    # constructor (serial and baud rate)
    def __init__(self, ser=None, baud=38400):
        self.ser = ser
        self.baud = baud
        self.lg = logging.getLogger(__name__) # TODO replace some prints with debugs
    
    # establishes usb serial connection to trax
    def connect(self):
        trax_ids = ["A1019O07", "FTBD1LEK"]
        for attempt in range(3):  # Retry 3 times
            ports = list_ports.comports()
            for port in ports:
                if port.serial_number in trax_ids:
                    try:
                        self.ser = serial.Serial(
                            port.device,
                            self.baud,
                            timeout=1,
                            write_timeout=1
                        )
                        self.ser.reset_input_buffer()
                        self.ser.reset_output_buffer()
                        time.sleep(0.1)  # Allow device to initialize
                        print(f"TRAX CONNECTED: {port.device}")
                        return True
                    except Exception as e:
                        print(f"Connection failed: {e}")
            time.sleep(0.5)  # Wait before retry
        print("NO TRAX FOUND AFTER 3 ATTEMPTS")
        return False

    # closes serial connection
    def close(self):
        self.ser.close()
    
    # prints information about using the TRAX wrapper class
    @staticmethod
    def help():
        print("This is the TRAX python wrapper class to interface with the PNI TRAX 2 AHRSE sensor.")
        print("Please refer to Chapter 7 'Operation with PNI Binary Protocol' of the data sheet:\nhttps://www.pnisensor.com/wp-content/uploads/TRAX2-User-Manual.pdf\n")
        print("SETUP")
        print("To use this wrapper class, start with the following:\ntrax = TRAX()\ntrax.connect()\n#your code here\ntrax.close()\n")
        print("SENDING DATA")
        print("trax.send_packet(frame ID, payload)\nUsage: frame ID should be an int from the table or the string name of the command, and payload should be a tuple or array of values.")
        print("This function returns nothing.\n")
        print("RECEIVING DATA")
        print("trax.recv_packet()\nUsage: In most cases, you can leave the parameters empty. If the command says it has ID specific values, just pass the payload from whatever previous command this one is answering.")
        print("This function returns a tuple of values according to the datagram in the data sheet.\n")
        print("DATAGRAM")
        print("[ byte count uint16 ] [ frame ID uint8 ] [ payload (optional) ] [ CRC uint16 ]\n\n")


    # returns and prints byte array packet based on frame ID and payload in trax-readable format
    @staticmethod
    def get_packet(frameID, payload=None): # datagram: [ byte count uint16 ] [ frame ID uint8 ] [ payload (opt) ] [ CRC uint16 ]
        payload_bytes = TRAX.get_payload_bytes(frameID, payload)
        byte_count = 5 + TRAX.calc_byte_count(payload_bytes) # 2 bits byte count + 1 bit ID + payload + 2 bits CRC

        packet  = byte_count.to_bytes(2, byteorder='big')
        packet += frameID.to_bytes(1, byteorder='big')
        packet += payload_bytes
        packet += TRAX.calc_CRC(packet).to_bytes(2, byteorder='big')
        return packet
    
    # generates a byte array based on frameID and tuple/array of specification IDs
    @staticmethod
    def get_payload_bytes(frameID, payload=None):
        """Generate a byte array based on frameID and payload specifications.
        Args:
            frameID (int): The frame ID (e.g., 7 for kGetConfig).
            payload (tuple): Data to pack. Structure depends on frameID.
    
        Returns:
            bytearray: Packed bytes, or empty if no payload.
        """
        if payload is None:
            return bytearray()

        # Define encoding rules for each frameID
        ENCODING_RULES = {
            7: "B",       # kGetConfig: UInt8
            10: "I",      # kStartCal: UInt32
            13: "BB",     # kGetFIRFilters: UInt8 UInt8
            17: "I",      # kUserCalSampleCount: UInt32
            24: "BBff",   # kSetAcqParams: UInt8 UInt8 Float64 Float64
            43: "BB",     # kCopyCoeffSet: UInt8 UInt8
            79: "B",      # kSetFunctionalMode: UInt8
            107: "B",     # kSetDistortMode: UInt8
            119: "B",     # kSetMagTruthMethod: UInt8
            128: "Bf",    # kSetMergeRate: UInt8 Float32
            3: lambda p: "B" + "B" * (len(p) - 1),  # kSetDataComponents: Dynamic
            6: lambda p: "B" + TRAX.struct_chars(p[1:]),
            12: lambda p: "BBB" + "F" * p[2] if p[2] in {0, 4, 8, 16, 32} else ""
        }

        # Get the encoding rule
        encode_str = ">"  # Big-endian
        rule = ENCODING_RULES.get(frameID)

        if rule is None:
            raise ValueError(f"Unsupported frameID: {frameID}")

        # Handle lambda rules (dynamic encoding)
        if callable(rule):
            encode_str += rule(payload)
        else:
            encode_str += rule

        # Validate payload length matches encoding
        expected_len = struct.calcsize(encode_str)
        if len(payload) != expected_len:
            raise ValueError(f"Payload length mismatch for frameID {frameID}: "
                             f"expected {expected_len}, got {len(payload)}")

        return bytearray(struct.pack(encode_str, *payload))

    # transmits packet over USB, frame ID is an int, tuple/array for payload values if applicable
    def send_packet(self, frameID, payload=None):
        self.ser.reset_input_buffer()  # Clear any stale input
        self.ser.reset_output_buffer() # Clear output
        
        fID = frameID if isinstance(frameID, int) else TRAX.get_frame_id(frameID)
        packet = self.get_packet(fID, payload)
        
        try:
            self.ser.write(packet)
            print("TRANSMISSION:\t", self.parse_bytes(packet))
        except serial.SerialTimeoutException:
            print("ERROR: Write timeout")
        except serial.SerialException as e:
            print(f"Serial error: {e}")

    # returns an int for the frame ID given the string name of a frame
    @staticmethod
    def get_frame_id(frameID_str):
        """Convert a frame ID string to its corresponding numeric value.
    
        Args:
            frameID_str (str): The frame ID string (e.g., "kGetModInfo").

        Returns:
            int: Numeric frame ID, or None if invalid.
        """
        frame_id_map = {
            "kGetModInfo": 1,
            "kSetDataComponents": 3,
            "kGetData": 4,
            "kSetConfig": 6,
            "kGetConfig": 7,
            "kSave": 9,
            "kStartCal": 10,
            "kStopCal": 11,
            "kSetFIRFilters": 12,
            "kGetFIRFilters": 13,
            "kPowerDown": 15,
            "kStartContinuousMode": 21,
            "kStopContinuousMode": 22,
            "kSetAcqParams": 24,
            "kGetAcqParams": 25,
            "kTakeUserCalSample": 31,
            "kFactoryMagCoeff": 29,
            "kTakeUserSample": 31,
            "kFactoryAccelCoeff": 36,
            "kCopyCoeffSet": 43,
            "kSerialNumber": 52,
            "kSetFunctionalMode": 79,
            "kGetFunctionalMode": 80,
            "kSetDistortMode": 107,
            "kGetDistortMode": 108,
            "kSetResetRef": 110,
            "kSetMagTruthMethod": 119,
            "kGetMagTruthMethod": 120,
            "kSetMergeRate": 128,
            "kGetMergeRate": 129,
        }
        return frame_id_map.get(frameID_str, None)
    
    # receives and reads packet from TRAX, checks checksum, returns a tuple of values read 
    # if the datagram includes ID Specific types, pass the payload tuple/array from the prior send_packet() call that made the query
    def recv_packet(self, payload=None, timeout=0.5):
        print("\n=== DEBUGGING recv_packet ===")
        print(f"Bytes in waiting: {self.ser.in_waiting}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Print buffer contents before reading
            buffer_contents = self.ser.read_all()
            if buffer_contents:
                print(f"Pre-read buffer: {buffer_contents.hex(' ')}")
                self.ser.write(buffer_contents)  # Put back for proper reading
            
            try:
                header = self.ser.read(3)
                if not header:
                    print("No header received")
                    continue
                    
                print(f"Header bytes: {header.hex(' ')}")

                byteCount = struct.unpack(">H", header[:2])[0]
                frameID = header[2]

                # Calculate remaining bytes to read
                remaining_bytes = byteCount - 1  # Already read ID
                if remaining_bytes < 2:  # Need at least 2 bytes for CRC
                    continue

                # Read payload + CRC
                rest = self.ser.read(remaining_bytes)
                if len(rest) != remaining_bytes:
                    continue

                packet = header + rest
                print(f"RECEIVED: {self.parse_bytes(packet)}")

                if not self.verify_CRC(packet):
                    print("CRC FAILED")
                    continue

                return self.read_packet(packet, payload)

            except serial.SerialException as e:
                print(f"Serial error: {e}")
                break
            except struct.error as e:
                print(f"Unpack error: {e}")
                continue

        print("TIMEOUT: No valid packet received")
        return None

    # returns a struct lib char string based on payload automatically
    @staticmethod
    def struct_chars(payload):
        encode_str = ""
        for p in payload:
            if type(p) ==   type(1):    encode_str += "B" # UInt8
            elif type(p) == type(1.0):  encode_str += "f" # Float32
            elif type(p) == type(True): encode_str += "B" # Boolean represented as UInt8
            else:                       encode_str += "f" # Default - Float32
        return encode_str
    
    @staticmethod
    def componentID_type(compID):
        """Return the struct format character for a given Component ID.
    
        Args:
            compID (int): The component ID (e.g., 5 for kHeading).
    
        Returns:
            str: struct format character (e.g., "f" for Float32).
                 Defaults to "f" (Float32) for unknown IDs.
        """
        componentID_map = {
            # Float32 components
            5: "f",    # kHeading
            7: "f",    # kTemperature
            21: "f",   # kAccelX
            22: "f",   # kAccelY
            23: "f",   # kAccelZ
            24: "f",   # kPitch
            25: "f",   # kRoll
            27: "f",   # kMagX
            28: "f",   # kMagY
            29: "f",   # kMagZ
            74: "f",   # kGyroX
            75: "f",   # kGyroY
            76: "f",   # kGyroZ
            77: "4f",  # kQuaternion (4x Float32)
        
            # Non-float components
            8: "?",    # kDistortion (Boolean)
            9: "?",    # kCalStatus (Boolean)
            79: "B",   # kHeadingStatus (UInt8)
        }
        return componentID_map.get(compID, "f")  # Default to Float32


    @staticmethod
    def configID_type(configID):
        """Return the struct format character for a given Config ID.
    
        Args:
            configID (int): The configuration ID (e.g., 1 for kDeclination).
    
        Returns:
            str: struct format character (e.g., "f" for Float32).
            Defaults to "B" (UInt8) for unknown IDs.
        """
        configID_map = {
            # Float32
            1: "f",   # kDeclination
        
            # Booleans
            2: "?",   # kTrueNorth
            6: "?",    # kBigEndian
            13: "?",   # kUserCalAutoSampling
            15: "?",   # kMilOut
            16: "?",   # kHPRDuringCal
        
            # UInt8
            10: "B",   # kMountingRef
            14: "B",   # kBaudRate
        
            # UInt32
            12: "I",   # kUserCalNumPoints
            18: "I",   # kMagCoeffSet
            19: "I",   # kAccelCoeffSet
        }
        return CONFIG_ID_TO_FORMAT.get(configID, "B")  # Default to UInt8

    # parses bytes to make legible string
    @staticmethod
    def parse_bytes(bytes):
        return "".join(f"{b:02X} " for b in bytes)        

    # converts a uint (that was converted from bytes) to a string, taking the number followed by the bit size (default is uint32)
    @staticmethod
    def uint_to_str(num, size=32):
        return num.to_bytes(int(size/8), 'big').decode('ascii', errors='ignore')
    
    # calculates integer byte count based on packet
    @staticmethod
    def calc_byte_count(packet):
        count = 0
        for _ in packet: count += 1
        return count
    
    # verifies a packet (in bytes) based on its checksum
    @staticmethod
    def verify_CRC(packet):
        index = len(packet) - 2
        packet_crc = struct.unpack(">H", packet[index:])[0] # CRC decoded from last 2 bits in packet
        test_crc = TRAX.calc_CRC(packet[:index]) # CRC calculated from byte count, ID, payload in packet
        
        return packet_crc == test_crc
    
    # calculates checksum (CRC-16) of packet (based on data sheet C fxn)
    @staticmethod
    def calc_CRC(packet):
        crc = 0xFFFF
        for byte in packet:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    """
    DATA SHEET CRC FXN:
    UInt16 CommProtocol::CRC(void * data, UInt32 len)
    {
        UInt8 * dataPtr = (UInt8 *)data;
        UInt32 index = 0;
        UInt16 crc = 0;
        while (len--)
        {
            crc = (unsigned char)(crc >> 8) | (crc << 8);
            crc ^= dataPtr[index++];
            crc ^= (unsigned char)(crc & 0xff) >> 4;
            crc ^= (crc << 8) << 4;
            crc ^= ((crc & 0xff) << 4) << 1;
        }
        return crc;
    }
    """
