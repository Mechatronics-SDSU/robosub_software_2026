import serial
import time

class GPSInterface:

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object

    def parse_gpgga(self, data):
        parts = data.split(',')
        if len(parts) < 15:
            return
        self.shared_memory_object.gps_latitude = parts[2]
        self.shared_memory_object.gps_longitude = parts[4]

    def parse_gprmc(self, data):
        parts = data.split(',')
        if len(parts) < 12:
            return "Invalid GPRMC data"
        
        self.shared_memory_object.gps_latitude = parts[3]
        self.shared_memory_object.gps_longitude = parts[5]

    def run_loop(self):
        port = '/dev/tty.usbmodem101'
        baud_rate = 9600
        
        try:
            ser = serial.Serial(port, baud_rate, timeout=1)
            time.sleep(2)  # Wait for the serial connection to initialize
            
            while True:
                line = ser.readline().decode('ascii', errors='replace').strip()
                
                if line.startswith('$GPGGA'):
                    print(self.parse_gpgga(line))
                elif line.startswith('$GPRMC'):
                    print(self.parse_gprmc(line))
        
        except serial.SerialException as e:
            print(f"Error: {e}")
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            if ser.is_open:
                ser.close()

# Functions for main to print out values

def parse_gpgga(data):
    parts = data.split(',')
    if len(parts) < 15:
        return "Invalid GPGGA data"
    
    time_utc = parts[1]
    latitude = parts[2]
    lat_direction = parts[3]
    longitude = parts[4]
    lon_direction = parts[5]
    fix_quality = parts[6]
    num_satellites = parts[7]
    horizontal_dilution = parts[8]
    altitude = parts[9]
    altitude_units = parts[10] 
    
    return f"""
    Time (UTC): {time_utc}
    Latitude: {latitude} {lat_direction}
    Longitude: {longitude} {lon_direction}
    Fix Quality: {fix_quality}
    Number of Satellites: {num_satellites}
    Horizontal Dilution of Precision: {horizontal_dilution}
    Altitude: {altitude} {altitude_units}
    """

def parse_gprmc(data):
    parts = data.split(',')
    if len(parts) < 12:
        return "Invalid GPRMC data"
    
    time_utc = parts[1]
    status = parts[2]
    latitude = parts[3]
    lat_direction = parts[4]
    longitude = parts[5]
    lon_direction = parts[6]
    speed_over_ground = parts[7]
    course_over_ground = parts[8]
    date = parts[9]
    
    return f"""
    Time (UTC): {time_utc}
    Status: {status}
    Latitude: {latitude} {lat_direction}
    Longitude: {longitude} {lon_direction}
    Speed Over Ground: {speed_over_ground}
    Course Over Ground: {course_over_ground}
    Date: {date}
    """

def main():
    # Print out values

    port = '/dev/tty.usbmodem101'
    baud_rate = 9600
    
    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        time.sleep(2)  # Wait for the serial connection to initialize
        
        while True:
            line = ser.readline().decode('ascii', errors='replace').strip()
            
            if line.startswith('$GPGGA'):
                print(parse_gpgga(line))
            elif line.startswith('$GPRMC'):
                print(parse_gprmc(line))
    
    except serial.SerialException as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    # Print out values
    gps = GPSInterface()
    gps.main()