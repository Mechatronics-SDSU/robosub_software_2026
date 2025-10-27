import struct
import logging
import serial
from serial.tools import list_ports

"""
    Created by Ryan Sundermeyer
    https://github.com/rsunderr
    mechatronics@sundermeyer.com
"""


# set up module level logger
LEVEL = logging.INFO
logger = logging.getLogger(__name__)
logger.setLevel(LEVEL)

# create console handler if it doesnt exist
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LEVEL)
    
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # add handler to logger
    logger.addHandler(console_handler)

class TRAX:
    """
    Wrapper class for trax-related functions
    """
    # CONNECTION AND SETUP ------------------------------------------------------------------------------------------------------------------------------------------------
    def __init__(self, ser=serial.Serial(), baud: int=38400):
        """
        Constructor (serial, baud rate)
        """
        self.ser: serial.Serial = ser
        self.baud: int = baud
    
    def connect(self) -> None:
        """
        Establishes usb serial connection to trax
        """
        trax1: str = "A1019O07"
        trax2: str = "FTBD1LEK"
        ports: list = list_ports.comports()
        for port in ports:
            if port.serial_number == trax1 or port.serial_number == trax2: # connect to a trax
                try:
                    self.ser = serial.Serial(port.device, self.baud, timeout=1)
                    logger.info(f"TRAX CONNECTED: {port.device}")
                    return
                except:
                    logger.critical("TRAX FOUND, UNABLE TO CONNECT")
                    return
        logger.critical("NO TRAX FOUND")

    
    def close(self) -> None:
        """
        Closes serial connection to trax
        """
        self.ser.close()

    # RECEVING DATA ------------------------------------------------------------------------------------------------------------------------------------------------
    def recv_packet(self, payload: list | tuple | None = None) -> tuple:
        """
        Receives and reads packet from TRAX, checks checksum, returns a tuple of values read 
        If the datagram includes ID Specific types, pass the payload tuple/array from the prior send_packet() 
        call that made the query (otherwise no need for 2nd parameter)
        """
        packet: bytes = self.ser.read(2) # read first 2 bytes to get byte count
        usable_payload: tuple = tuple(payload) if payload is not None else () # make usable payload tuple for fxn call
        byteCount: int = struct.unpack(">H", packet)[0] # get byte count
        if byteCount < 5: # invalid byte count, warn user and stop fxn
            logger.critical("INVALID BYTE COUNT RECEIVED")
            raise Exception("INVALID BYTE COUNT RECEIVED")
        restOfPacket: bytes = self.ser.read(byteCount - 2) # continue reading rest of packet based on byte count
        if restOfPacket != None: packet += restOfPacket # concatenate rest of packet bytes

        if packet == b'': # if packet is empty, warn user and stop fxn
            logger.critical("NO MESSAGE RECEIVED")
            raise Exception("NO MESSAGE RECEIVED")

        log_string: str = f"RECEIVED:\t{TRAX.parse_bytes(packet)}"
        response: tuple = TRAX.read_packet(packet, usable_payload) # read packet into tuple of values

        verified: bool = TRAX.verify_CRC(packet) # verify packet using checksum
        if verified:
            log_string += f"\tCHECKSUM VALID"
            logger.info(log_string)
            return response
        else:
            logger.critical("CORRUPTED PACKET: CHECKSUM FAILED")
            raise Exception("CORRUPTED PACKET: CHECKSUM FAILED")
    
    @staticmethod
    def read_packet(packet: bytes, payload: list | tuple) -> tuple:
        """
        Reads packet of bytes in trax-readable format, returns tuple of values read
        If the datagram includes ID Specific types, pass the payload tuple from the prior send_packet() call 
        that made the query
        """
        frameID: int = packet[2] # get frame ID from packet (bytes)
        decode_str: str = ">HB" # big endian, byte count, ID
        match frameID:
            # NORMAL FRAMES
            case 2:     decode_str += "II" # kGetModInfoResp    
            case 16:    decode_str += "H" # kSaveDone
            case 18:    decode_str += "ffffff" # kUserCalScore
            case 27:    decode_str += "BBff" # kSetAcqParamsResp
            case 53:    decode_str += "I" # kSerialNumberResp
            case 81:    decode_str += "B" # kGetFunctionalModeResp
            case 109:   decode_str += "B" # kGetDistortionModeResp
            case 121:   decode_str += "B" # kGetMagTruthMethodResp
            # ID SPECIFIC FRAMES: TODO: not sure if quaternion works
            case 130:   decode_str += "Bf" # kGetMergeRateResp
            case 5: # kGetDataResp
                decode_str += "B" # ID Count
                id_list = payload[1:]
                for id in id_list: # NOTE: expected tuple payload from prior kSetDataComponents call: (ID count, ID, ID, ...)
                    decode_str += "B" # reads: ID Count, ID, Status, ID, Status, ...
                    decode_str += TRAX.componentID_type(id) # gets struct lib char based on Component ID
            case 8: # kGetConfigResp
                decode_str += "B" + TRAX.configID_type(payload[0]) # NOTE: expected tuple payload from prior kGetConfig call: (Config ID,)
            case 14: # kGetFIRFiltersResp
                decode_str += "BBB"
                N = payload[2] # NOTE: number of float 64 filter vals in payload based on 3rd bit of payload from prior kSetFirFilters call: (x,x, N, ...)
                if N == 0 or N == 4 or N == 8 or N == 16 or N == 32:
                    for _ in range(N): decode_str += "F" # meant to be 0, 4, 8, 16, or 32 tap filter values
            # ID # 19, 23, 26, 28, 30, 37, 44 have no payload
        
        decode_str += "H" # CRC
        try:
            return struct.unpack(decode_str, packet)
        except:
            logger.warning("WARNING: CORRUPTED PACKET")
            raise Exception("CORRUPTED PACKET")
    
    # SENDING DATA ------------------------------------------------------------------------------------------------------------------------------------------------
    def send_packet(self, frameID: int | str, payload: list | tuple | None = None) -> None:
        """
        Transmits packet over USB, frame ID is an int or string (name), tuple/array for payload values if applicable
        """
        usable_payload: tuple = tuple(payload) if payload is not None else () # make usable payload tuple for fxn call
        usable_frameID: int = TRAX.get_frame_id(frameID) if type(frameID) == str else int(frameID) # if frameID is string, get int value with fxn

        packet: bytes = TRAX.create_packet(usable_frameID, usable_payload) # create packet in bytes
        self.ser.write(packet) # send packet over serial
        logger.info(f"TRANSMISSION:\t{TRAX.parse_bytes(packet)}") # print transmission contents

    @staticmethod
    def create_packet(frameID: int, payload: list | tuple) -> bytes: # datagram: [ byte count uint16 ] [ frame ID uint8 ] [ payload (opt) ] [ CRC uint16 ]
        """
        Returns and prints bytes packet based on frame ID and payload in trax-readable format
        """
        payload_bytes: bytes = TRAX.get_payload_bytes(frameID, payload)
        byte_count: int = 5 + TRAX.calc_byte_count(payload_bytes) # 2 bits byte count + 1 bit ID + payload + 2 bits CRC

        packet: bytes = byte_count.to_bytes(2, byteorder='big')
        packet += frameID.to_bytes(1, byteorder='big')
        packet += payload_bytes
        packet += TRAX.calc_CRC(packet).to_bytes(2, byteorder='big')
        return packet
    
    @staticmethod
    def get_payload_bytes(frameID: int, payload: list | tuple) -> bytes:
        """
        Generates bytes for payload based on frameID and tuple/array of specification IDs
        """
        payload_bytes = bytes()
        encode_str: str = ">" # struct pack encode string (big endian)
        match frameID:
            case 7:     encode_str += "B" # kGetConfig - UInt8 
            case 10:    encode_str += "I" # kStartCal - UInt32
            case 13:    encode_str += "BB" # kGetFIRFilters - UInt8 UInt8
            case 17:    encode_str += "I" # kUserCalSampleCount - UInt32
            case 24:    encode_str += "BBff" # kSetAcqParams - UInt8 UInt8 Float64 Float64
            case 43:    encode_str += "BB" # kCopyCoeffSet - UInt8 UInt8
            case 79:    encode_str += "B" # kSetFunctionalMode - UInt8 
            case 107:   encode_str += "B" # kSetDistortMode - UInt8 
            case 119:   encode_str += "B" # kSetMagTruthMethod - UInt8 
            case 128:   encode_str += "Bf" # kSetMergeRate - UInt8 Float32
            # ID SPECIFIC FRAMES: TODO: not sure if quaternion works
            case 3: # kSetDataComponents - UInt8 + ID Specific...
                encode_str += "B" # component count
                for _ in payload[1:]: # NOTE: expected tuple payload: (ID count, ID, ID, ...)
                    encode_str += "B"
            case 6:     encode_str += "B" + TRAX.struct_chars(payload[1:]) # kSetConfig - UInt8 + ID Specific...
            case 12: # kSetFIRFilters - ID Specific
                encode_str += "BBB"
                N = payload[2] # NOTE: number of Float64 filter vals in payload based on 3rd bit of payload: (x,x, N, ...)
                if N == 0 or N == 4 or N == 8 or N == 16 or N == 32:
                    for _ in range(N): encode_str += "F" # meant to be 0, 4, 8, 16, or 32 tap filter values
            # ID # 1, 4, 9, 11, 15, 21, 22, 25, 29, 31, 36, 52, 80, 108, 110, 120, 129 have no payload
        payload_bytes: bytes = struct.pack(encode_str, *payload)
        return payload_bytes

    @staticmethod
    def get_frame_id(frameID_str: str) -> int:
        """
        Returns an int for the frame ID given the string name of a frame
        Used for sending data
        """
        match frameID_str:
            case "kGetModInfo":         return 1
            case "kSetDataComponents":  return 3
            case "kGetData":            return 4
            case "kSetConfig":          return 6
            case "kGetConfig":          return 7
            case "kSave":               return 9
            case "kStartCal":           return 10
            case "kStopCal":            return 11
            case "kSetFIRFilters":      return 12
            case "kGetFIRFilters":      return 13
            case "kPowerDown":          return 15
            case "kStartContinuousMode":return 21
            case "kStopContinuousMode": return 22
            case "kSetAcqParams":       return 24
            case "kGetAcqParams":       return 25
            case "kTakeUserCalSample":  return 31
            case "kFactoryMagCoeff":    return 29
            case "kTakeUserSample":     return 31
            case "kFactoryAccelCoeff":  return 36
            case "kCopyCoeffSet":       return 43
            case "kSerialNumber":       return 52
            case "kSetFunctionalMode":  return 79
            case "kGetFunctionalMode":  return 80
            case "kSetDistortMode":     return 107
            case "kGetDistortMode":     return 108
            case "kSetResetRef":        return 110
            case "kSetMagTruthMethod":  return 119
            case "kGetMagTruthMethod":  return 120
            case "kSetMergeRate":       return 128
            case "kGetMergeRate":       return 129
            case _: 
                logger.error("Invalid Frame ID")
                raise Exception("Invalid Frame ID")
    
    # HELPER FUNCTIONS ------------------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def struct_chars(payload: list | tuple) -> str:
        """
        Returns a struct lib char string based on payload automatically
        """
        encode_str: str = ""
        for p in payload:
            if type(p)   == type(1):    encode_str += "B" # UInt8
            elif type(p) == type(1.0):  encode_str += "f" # Float32
            elif type(p) == type(True): encode_str += "B" # Boolean represented as UInt8
            else:                       encode_str += "f" # Default - Float32
        return encode_str
    
    @staticmethod
    def componentID_type(compID: int) -> str:
        """
        Returns the struct library character based on the Component ID (which can then be used for unpacking)
        """
        match compID:
            case 5:     return "f"   # kHeading - Float32
            case 24:    return "f"   # kPitch - Float32
            case 25:    return "f"   # kRoll - Float32
            case 77:    return "4f"  # kQuaternion - 4x Float32
            case 8:     return "?"   # kDistortion - Boolean
            case 79:    return "B"   # kHeadingStatus - UInt8
            case 7:     return "f"   # kTemperature - Float32
            case 9:     return "?"   # kCalStatus - Boolean
            case 21:    return "f"   # kAccelX - Float32
            case 22:    return "f"   # kAccelY - Float32
            case 23:    return "f"   # kAccelZ - Float32
            case 27:    return "f"   # kMagX - Float32
            case 28:    return "f"   # kMagY - Float32
            case 29:    return "f"   # kMagZ - Float32
            case 74:    return "f"   # kGyroX - Float32
            case 75:    return "f"   # kGyroY - Float32
            case 76:    return "f"   # kGyroZ - Float32
            case _:     return "f"   # Default - UInt8
    
    @staticmethod
    def configID_type(configID: int) -> str:
        """
        Returns the struct library character based on the config ID
        """
        match configID:
            case 1:     return "f" # kDeclination - Float32
            case 2:     return "?" # kTrueNorth - Boolean
            case 6:     return "?" # kBigEndian - Boolean
            case 10:    return "B" # kMountingRef - UInt8
            case 12:    return "I" # kUserCalNumPoints - UInt32
            case 13:    return "?" # kUserCalAutoSampling - Boolean
            case 14:    return "B" # kBaudRate - UInt8
            case 15:    return "?" # kMilOut - Boolean
            case 16:    return "?" # kHPRDuringCal - Boolean
            case 18:    return "I" # kMagCoeffSet - UInt32
            case 19:    return "I" # kAccelCoeffSet - UInt32
            case _:     return "B" # Default - UInt8
    
    @staticmethod
    def parse_bytes(bytes: bytes) -> str:
        """
        Parses bytes to make legible string
        """
        return "".join(f"{b:02X} " for b in bytes)        

    @staticmethod
    def uint_to_str(num: int, size=32) -> str:
        """
        Converts a uint (that was converted from bytes) to a string, taking the number followed by the bit 
        size (default is uint32)
        """
        return num.to_bytes(int(size/8), 'big').decode('ascii', errors='ignore')
    
    @staticmethod
    def calc_byte_count(packet: bytes) -> int:
        """
        Calculates integer byte count based on packet
        """
        count: int = 0
        for _ in packet: count += 1
        return count
    
    @staticmethod
    def verify_CRC(packet: bytes) -> bool:
        """
        Verifies a packet (in bytes) based on its checksum
        """
        index: int = len(packet) - 2
        packet_crc: int = struct.unpack(">H", packet[index:])[0] # CRC decoded from last 2 bits in packet
        test_crc: int = TRAX.calc_CRC(packet[:index]) # CRC calculated from byte count, ID, payload in packet

        return packet_crc == test_crc
    
    @staticmethod
    def calc_CRC(packet: bytes) -> int:
        """
        Calculates checksum (CRC-16) of packet (based on data sheet C fxn)
        """
        crc: int = 0
        for byte in packet:
            crc = ((crc >> 8) & 0xFF) | ((crc << 8) & 0xFFFF)
            crc ^= byte
            crc ^= (crc & 0xFF) >> 4
            crc ^= (crc << 8) << 4
            crc ^= ((crc & 0xFF) << 4) << 1
            crc &= 0xFFFF # trim to 16 bit
        return int(crc)