import serial
import time
import numpy as np 

G_TO_MS2 = 9.80665
SAMPLING_RATE = 105.577698

#example acceleration output:  indexes 123 (raw): ax: 0.009, ay: 0.015, az: 1.006  indexes 456 (linear): ax: -0.000248118, ay: 0.0054822230000000005, az: 1.006592957

class SPARTON:
    def __init__(self, sparton = "/dev/tty.usbserial-FTG5PLPN", baud = 115200, num_bytes = 8, parity_bits = 'N', stop_bits = 1):
        self.sparton = sparton
        self.baud = baud
        self.num_bytes = num_bytes
        self.parity_bits = parity_bits
        self.stop_bits = stop_bits



        self.prev_t:    float = time.time()
        self.prev_timestamp   = None
        self.vel_x:     float = 0
        self.vel_y:     float = 0
        self.vel_z:     float = 0
        self.pos_x:     float = 0
        self.pos_y:     float = 0
        self.pos_z:     float = 0

        self.prev_x: float = 0 
        self.prev_y: float = 0 
        self.prev_z: float = 0 

        self.previous_yaw = 0
        self.previous_roll = 0
        self.previous_pitch = 0 

    def connect(self):
        try:
            self.ser = serial.Serial(port = self.sparton, baudrate = self.baud, bytesize = self.num_bytes, parity = self.parity_bits, stopbits = self.stop_bits, timeout = 1)
            
            #print line for acceleration, quaternion, compass (only have to send once per plugin)
            '''
            self.ser.write(b'1 accelp.p\r\n')
            self.ser.write(b'1 quat.p\r\n') 
            self.ser.write(b'1 compass.p\r\n') 
            self.ser.write(b'1 gyrop.p\r\n')
            '''
        except:
            print("ERROR: Sparton disconnected.")
            return


    def enable_compass(self):
        self.ser.write(b'1 compass.p\r\n')

    def enable_gyro(self):
        self.ser.write(b'1 gyrop.p\r\n')

    def enable_fusion_data(self):
        self.ser.write(b'1 gyrop.p\r\n')
        self.ser.write(b'1 accelp.p\r\n')



    def read_accel(self):
        if self.ser: #if connected run

            try:
                self.ser.write(b'1 accelp.p\r\n') #write to sparton command to print raw and linear acceleration 

                while True:

                    #format: first 7 outputs = timestamp, raw x,y,z, linear x,y,z
                    line = self.ser.readline().decode().strip()
                    #print(line)

                    if "AP" in line[0:2]: #only print lines with data
                        t:  float = time.time()
                        dt: float = t - self.prev_t
                        self.prev_t = t
                        
                        data = line[3:].split(',') #dont inlcude AP: in data

                        timestamp = int(data[0]) / 1000 #time in ms measuing how long the sparton has been plugged in


                        #indexes 4,5,6 are scaled to 1 g and are in units of mili gs
                        ax = float(data[4]) / 1000.0 #convert from mili gs to gs
                        ay = float(data[5]) / 1000.0
                        az = float(data[6]) / 1000.0
                        
                        #conver to meters per second squared
                        ax = ax * G_TO_MS2
                        ay = ay * G_TO_MS2
                        az = az * G_TO_MS2 - (9.80665)

                        #print(ax,ay,az)

                        dx: float = ax
                        dy: float = ay
                        dz: float = az

                        self.vel_x += dx * dt
                        self.vel_y += dy * dt
                        self.vel_z += dz * dt

                        self.pos_x += self.vel_x * dt
                        self.pos_y += self.vel_y * dt
                        self.pos_z += self.vel_z * dt


                        #print(f"timestamp: {timestamp} s, ax: {ax:.2f} m/s2, ay: {ay:.2f} m/s2, az: {az:.2f} m/s2")
                        print(f"position    x: {self.pos_x:.2f}, y: {self.pos_y:.2f}, z: {self.pos_z:.2f}")

    
            except KeyboardInterrupt: 
                self.ser.write(b'0 accelp.p\r\n') #stop sending data
                time.sleep(0.1)
                self.close()

            except Exception as e:
                print(f"Invalid Sparton data: {e}")





    def read_quat(self):
        if self.ser:

            try:
                self.ser.write(b'1 quat.p\r\n')

                while True:

                    #format QUAT:%f,%f,%f,%f  w,x,y,z
                    line = self.ser.readline().decode().strip()
                    #print(line)

                    if "QUAT" in line: #make sure reading quaternion data
                        t: float = time.time()
                        dt: float = t - self.prev_t
                        self.prev_t = t
 
                        
                        data = line[5:].split(',') #remove QUAT and parse data

                        w = float(data[0])
                        x = float(data[1])
                        y = float(data[2])
                        z = float(data[3])

                        self.angular_velocity(w, x, y, z, dt)

                        print(f"w: {w}, x: {x}, y: {y}, z: {z}")


            except KeyboardInterrupt:
                
                self.ser.write(b'0 quat.p\r\n') #stop quaternion data
                time.sleep(0.1)
                self.close()

            except Exception as e:
                print(f"invalid sparton data: {e}")



    def read_gyro(self):
        if self.ser:

            try:

                while True:
                    line = self.ser.readline().decode().strip()
                    if "GP" in line[0:2]:

                        data = line[3:].split(',')

                        timestamp = float(data[0]) / 1000


                        #Sparton's timer runs from plug in time so set to zero if first run
                        if self.prev_timestamp is None:
                            dt = 0 
                            self.prev_timestamp = timestamp
                            continue

                        else:
                            dt = timestamp - self.prev_timestamp

                        self.prev_timestamp = timestamp




                        #units of radians/sample so conver to rad/s
                        gyro_x = float(data[4]) * SAMPLING_RATE
                        gyro_y = float(data[5]) * SAMPLING_RATE
                        gyro_z = float(data[6]) * SAMPLING_RATE

                        
                        #calculate angular acceleration
                        angular_accel_x = (gyro_x - self.prev_x) / dt
                        angular_accel_y = (gyro_y - self.prev_y) / dt
                        angular_accel_z = (gyro_z - self.prev_z) / dt

                        #for next loop's accel calculation
                        self.prev_x = gyro_x
                        self.prev_y = gyro_y
                        self.prev_z = gyro_z


                        print(f"angular vel    x: {gyro_x:.2f}, y: {gyro_y:.2f}, z: {gyro_x:.2f}")
                        print(f"angular acc    x: {angular_accel_x:.2f}, y: {angular_accel_y:.2f}, z: {angular_accel_z:.2f}")



            except KeyboardInterrupt: 
                self.ser.write(b'0 gyrop.p\r\n') #stop sending data
                time.sleep(0.1)
                self.close()

            except Exception as e:
                print(f"Invalid Sparton data: {e}")






    def read_compass(self):
        if self.ser:

            try:
                self.ser.write(b'1 compass.p')

                while True:
                    line = self.ser.readline().decode().strip()

                    if "C," in line:
                        print(line)
                        data = line[2:].split(',')
                        
                        timestamp = float(data[0]) / 1000

                        #in degrees
                        pitch = float(data[1])
                        roll = float(data[2])
                        yaw = float(data[3])

                        print(f"timestamp: {timestamp}, pitch: {pitch:.2f}, roll: {roll:.2f}, yaw: {yaw:.2f}")

            except KeyboardInterrupt:

                self.ser.write(b'0 compass.p\r\n')
                self.close()

            except Exception as e:
                print(f"Invalid Sparton Data: {e}")



    '''
    for coinflip
    '''

    def read_compass_step(self):

        if self.ser:
            try:
                line = self.ser.readline().decode().strip()

                if "C," in line:

                        data = line[2:].split(',')
                        
                        timestamp = float(data[0]) / 1000

                        #in degrees
                        pitch = float(data[1])
                        roll = float(data[2])
                        yaw = float(data[3])

                        self.prev_timestamp = timestamp
                        self.previous_yaw = yaw
                        self.previous_pitch = pitch
                        self.previous_roll = roll


                        print(timestamp,pitch,roll,yaw)
                        

                        return timestamp,pitch,roll,yaw
                else: #if reading other line
                    return self.prev_timestamp,self.previous_pitch,self.previous_roll,self.previous_yaw

            except KeyboardInterrupt:

                self.ser.write(b'0 compass.p\r\n')
                self.close()

            except Exception as e:
                print(f"Invalid Sparton Data: {e}")

    def calc_reference(self, y):
        self.yaw_reference = y




    def get_data(self): #for sensor fusion algorithm
        if self.ser:
            self.ser.write(b'1 gryop.p\r\n')
            self.ser.write(b'1 accelp.p\r\n')

            try:
                line = self.ser.readline().decode().strip()
                

                if "GP" in line[0:2]:

                        data = line[3:].split(',')

                        timestamp = float(data[0]) / 1000


                        #Sparton's timer runs from plug in time so set to zero if first run
                        if self.prev_timestamp is None:
                            dt = 0 
                            self.prev_timestamp = timestamp
                            

                        else:
                            dt = timestamp - self.prev_timestamp

                        self.prev_timestamp = timestamp




                        #units of radians/sample so conver to rad/s
                        gyro_x = float(data[4]) * SAMPLING_RATE
                        gyro_y = float(data[5]) * SAMPLING_RATE
                        gyro_z = float(data[6]) * SAMPLING_RATE

                        
                        #calculate angular acceleration
                        angular_accel_x = (gyro_x - self.prev_x) / dt
                        angular_accel_y = (gyro_y - self.prev_y) / dt
                        angular_accel_z = (gyro_z - self.prev_z) / dt

                        #for next loop's accel calculation
                        self.prev_x = gyro_x
                        self.prev_y = gyro_y
                        self.prev_z = gyro_z


                if "AP" in line[0:2]:
                        t:  float = time.time()
                        dt: float = t - self.prev_t
                        self.prev_t = t
                        
                        data = line[3:].split(',') #dont inlcude AP: in data

                        timestamp = int(data[0]) / 1000 #time in ms measuing how long the sparton has been plugged in


                        #indexes 4,5,6 are scaled to 1 g and are in units of mili gs
                        ax = float(data[4]) / 1000.0 #convert from mili gs to gs
                        ay = float(data[5]) / 1000.0
                        az = float(data[6]) / 1000.0
                        
                        #conver to meters per second squared
                        ax = ax * G_TO_MS2
                        ay = ay * G_TO_MS2
                        az = az * G_TO_MS2 - (9.80665)

                        #print(ax,ay,az)

                        dx: float = ax
                        dy: float = ay
                        dz: float = az

                        self.vel_x += dx * dt
                        self.vel_y += dy * dt
                        self.vel_z += dz * dt

                        self.pos_x += self.vel_x * dt
                        self.pos_y += self.vel_y * dt
                        self.pos_z += self.vel_z * dt
 
                time = dt
                lin_accel = np.array([[ax], [ay], [az]])
                ang_accel = np.array([angular_accel_x], [angular_accel_y], [angular_accel_z])

                return time, lin_accel, ang_accel 


                

    
            except KeyboardInterrupt: 
                self.ser.write(b'0 accelp.p\r\n') #stop sending data
                self.ser.write(b'0 gyrop.p')
                time.sleep(0.1)
                self.close()




    def close(self): 
        self.ser.write(b'0 accelp.p\r\n')
        self.ser.write(b'0 quat.p\r\n')
        self.ser.write(b'0 compass.p\r\n')
        self.ser.write(b'0 gyro.p\r\n')
        self.ser.close()




def main():
    print("good")
   

if __name__ == '__main__':
    main()




