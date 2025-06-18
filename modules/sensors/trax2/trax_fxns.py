import struct
import logging
import serial
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
        trax1 = "A1019O07"
        trax2 = "FTBD1LEK"
        ports = list_ports.comports()
        for port in ports:
            if port.serial_number == trax1 or port.serial_number == trax2: # connect to a trax
                try:
                    self.ser = serial.Serial(port.device, self.baud, timeout=1)
                    print("TRAX CONNECTED: ", port.device)
                    return
                except:
                    self.lg.critical("TRAX FOUND, UNABLE TO CONNECT")
                    return
        self.lg.critical("NO TRAX FOUND")

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
        payload_bytes = bytearray()
        if payload == None: return payload_bytes # return empty payload if no payload tuple/array passed
        encode_str = ">" # struct pack encode string (big endian)
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
            # no payload: 1, 4, 9, 11, 15, 21, 22, 25, 29, 31, 36, 52, 80, 108, 110, 120, 129
        payload_bytes = struct.pack(encode_str, *payload)
        return payload_bytes

    # transmits packet over USB, frame ID is an int, tuple/array for payload values if applicable
    def send_packet(self, frameID, payload=None):
        fID = frameID
        if type(frameID) == type("str"): fID = TRAX.get_frame_id(frameID)

        packet = TRAX.get_packet(fID, payload)
        self.ser.write(packet)
        print("TRANSMISSION:\t", TRAX.parse_bytes(packet))

    # returs an int for the frame ID given the string name of a frame
    @staticmethod
    def get_frame_id(frameID_str):
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
            case _: print("Invalid Frame ID")
    
    # receives and reads packet from TRAX, checks checksum, returns a tuple of values read 
    # if the datagram includes ID Specific types, pass the payload tuple/array from the prior send_packet() call that made the query
    def recv_packet(self, payload=None):
        #packet = self.ser.readline() # read input message
        packet = self.ser.read(2)
        byteCount = struct.unpack(">H", packet)[0]
        restOfPacket = self.ser.read(byteCount - 2)
        if restOfPacket != None: packet += restOfPacket

        if packet == b'': # if packet is empty, warn user and stop fxn
            self.lg.critical("NO MESSAGE RECEIVED")
            return -1
        
        print("RECEIVED:\t", TRAX.parse_bytes(packet))
        response = TRAX.read_packet(packet, payload)

        verified = TRAX.verify_CRC(packet) # verify packet using checksum
        if verified:
            print("CHECKSUM VERIFIED")
            return response
        else:
            self.lg.critical("CORRUPTED PACKET: CHECKSUM FAILED")
            return -1
    
    # reads packet of bytes in trax-readable format, returns tuple of values read
    # if the datagram includes ID Specific types, pass the payload tuple from the prior send_packet() call that made the query
    @staticmethod
    def read_packet(packet, payload=None):
        #byteCount = struct.unpack(">H", packet[:2])[0]
        frameID = packet[2] # get frame ID from packet (bytes)
        decode_str = ">HB" # big endian, byte count, ID
        match frameID:
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

                #if id_count != len(id_list): print("INCORRECT NUMBER OF IDs IN PAYLOAD: DOES NOT MATCH ID COUNT")
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
            # 19, 23, 26, 28, 30, 37, 44 have no payload
        
        decode_str += "H" # CRC
        return struct.unpack(decode_str, packet)
    
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

    # returns the struct lib char based on the Component ID
    @staticmethod
    def componentID_type(compID):
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
    
    # returns the struct lib char based on the config ID
    @staticmethod
    def configID_type(configID):
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
        crc = 0
        for byte in packet:
            crc = ((crc >> 8) & 0xFF) | ((crc << 8) & 0xFFFF)
            crc ^= byte
            crc ^= (crc & 0xFF) >> 4
            crc ^= (crc << 8) << 4
            crc ^= ((crc & 0xFF) << 4) << 1
            crc &= 0xFFFF # trim to 16 bit
        return int(crc)

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