import serial
import time
import numpy as np 

G_TO_MS2 = 9.80665
SAMPLING_RATE = 105.577698

'''
This file is used to output only the data required for the sensor fusion algorithm. 

The file containing different commands is in modules/sensors/sparton
'''
#sparton gedc-6e: /dev/tty.usbserial-FTG5PLPN
#sparton gedc-6: /dev/tty.usbserial-FT9IZN46
#
class SPARTON_FUSION:
    def __init__(self, sparton, ser=serial.Serial(), baud = 115200, num_bytes = 8, parity_bits = 'N', stop_bits = 1):
        self.sparton = sparton
        self.baud = baud
        self.num_bytes = num_bytes
        self.parity_bits = parity_bits
        self.stop_bits = stop_bits
        self.ser: serial.Serial = ser



        self.prev_t:    float = time.time()
        self.prev_timestamp   = None
        self.dt:        float = 0
        self.ax:        float = 0
        self.ay:        float = 0
        self.az:        float = 0
        self.vel_x:     float = 0
        self.vel_y:     float = 0
        self.vel_z:     float = 0
        self.pos_x:     float = 0
        self.pos_y:     float = 0
        self.pos_z:     float = 0
        self.gyro_x:    float = 0
        self.gyro_y:    float = 0
        self.gyro_z:    float = 0

        
        self.yaw:       float = 0
        self.roll:      float = 0
        self.pitch:     float = 0




        self.gyro_vec = np.array([0.0, 0.0, 0.0])
        self.accel_vec = np.array([0.0, 0.0, 0.0])
        self.euler_vec = np.array([0.0, 0.0, 0.0])




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
            
        except Exception as e:
            print(f"ERROR: Sparton disconnected due to {e}.")


    
    def enable_fusion_data(self): #enable the output of gyroxyz, accelxyz, and roll pitch yaw for sensior fusion
        
        self.ser.write(b'1 gyrop.p\r\n')
        self.ser.write(b'1 accelp.p\r\n')
        self.ser.write(b'1 compass.p\r\n')


    def get_data(self, shared_data):
        if self.ser:

            try:

                while True:

                    try:

                        line = self.ser.readline().decode("utf-8", errors="ignore").strip()

                        #each line sent from sparton has code at start to determine what data is sent.
                        if "GP" in line[0:2]:

                            data = line[3:].split(',')

                            timestamp = float(data[0]) / 1000


                            #Sparton's timer runs from plug in time so set to zero if first run
                            if self.prev_timestamp is None:
                                self.dt = 0 
                                self.prev_timestamp = timestamp


                            else:
                                self.dt = timestamp - self.prev_timestamp

                                self.prev_timestamp = timestamp


                            #units of radians/sample so conver to rad/s
                            gyro_x = float(data[4]) * SAMPLING_RATE
                            gyro_y = float(data[5]) * SAMPLING_RATE
                            gyro_z = float(data[6]) * SAMPLING_RATE

                            self.gyro_x = gyro_x
                            self.gyro_y = gyro_y
                            self.gyro_z = gyro_z


                            gyro_vec = np.array([self.gyro_x, self.gyro_y, self.gyro_z])

                            self.gyro_vec = gyro_vec

                            shared_data["gyro_vec"] = self.gyro_vec 

                            time.sleep(.01)



                            



                        if "AP" in line[0:2]:



                            data = line[3:].split(',') #dont inlcude AP: in data

                            timestamp = int(data[0]) / 1000 #time in ms measuing how long the sparton has been plugged in

                            if self.prev_timestamp is None:
                                self.dt = 0 
                                


                            else:
                                self.dt = timestamp - self.prev_timestamp


                            self.prev_timestamp = timestamp


                            #indexes 4,5,6 are scaled to 1 g and are in units of mili gs
                            ax = float(data[4]) / 1000.0 #convert from mili gs to gs
                            ay = float(data[5]) / 1000.0
                            az = float(data[6]) / 1000.0

                            #conver to meters per second squared
                            ax_converted = ax * G_TO_MS2
                            ay_converted = ay * G_TO_MS2
                            az_converted = az * G_TO_MS2 

                            #test when to subtract gravity vector, might want to do it after algorithm summation
                            self.ax = ax_converted
                            self.ay = ay_converted
                            self.az = az_converted - G_TO_MS2 

                            accel_vec = np.array([self.ax, self.ay, self.az])

                            self.accel_vec = accel_vec
     
                            
                            shared_data["accel_vec"] = self.accel_vec
                            shared_data["dt"] = self.dt
                            time.sleep(.01)
                            

                            


                        if "C," in line:

                            data = line[2:].split(',')

                            timestamp = float(data[0]) / 1000

                            if self.prev_timestamp is None:
                                self.dt = 0 
                                self.prev_timestamp = timestamp


                            else:
                                self.dt = timestamp - self.prev_timestamp
                                self.prev_timestamp = timestamp

                            #in degrees
                            pitch = float(data[1])
                            roll = float(data[2])
                            yaw = float(data[3])

                            self.pitch = pitch
                            self.roll = roll 
                            self.yaw = yaw

                            euler_vec = np.array([self.yaw, self.pitch, self.roll])

                            self.euler_vec = euler_vec

                            shared_data["euler_vec"] = self.euler_vec
                            time.sleep(.01)
                        


                    except Exception as e:
                        print(f"Invalid Sparton Data: {e}")
                        

            except KeyboardInterrupt: 
                self.ser.write(b'0 accelp.p\r\n') #stop sending data
                self.ser.write(b'0 gyrop.p\r\n')
                self.ser.write(b'0 compass.p\r\n')
                

                self.ser.close()

                


    def get_data_test(self): #used for testing sensor output as main process
        if self.ser:

            try:
                while True:

                    try:

                        line = self.ser.readline().decode().strip()
                        #print(line)

                        #each line sent from sparton has code at start to determine what data is sent.
                        if "GP" in line[0:2]:

                            data = line[3:].split(',')

                            timestamp = float(data[0]) / 1000


                            #Sparton's timer runs from plug in time so set to zero if first run
                            if self.prev_timestamp is None:
                                self.dt = 0 
                                self.prev_timestamp = timestamp


                            else:
                                self.dt = timestamp - self.prev_timestamp

                                self.prev_timestamp = timestamp


                            #units of radians/sample so conver to rad/s
                            gyro_x = float(data[4]) * SAMPLING_RATE
                            gyro_y = float(data[5]) * SAMPLING_RATE
                            gyro_z = float(data[6]) * SAMPLING_RATE

                            self.gyro_x = gyro_x
                            self.gyro_y = gyro_y
                            self.gyro_z = gyro_z


                            gyro_vec = np.array([self.gyro_x, self.gyro_y, self.gyro_z])

                            self.gyro_vec = gyro_vec

                            print(f"gyro {self.gyro_vec}")



                            



                        if "AP" in line[0:2]:



                            data = line[3:].split(',') #dont inlcude AP: in data

                            timestamp = int(data[0]) / 1000 #time in ms measuing how long the sparton has been plugged in

                            if self.prev_timestamp is None:
                                self.dt = 0 
                                self.prev_timestamp = timestamp


                            else:
                                self.dt = timestamp - self.prev_timestamp


                            #indexes 4,5,6 are scaled to 1 g and are in units of mili gs
                            ax = float(data[4]) / 1000.0 #convert from mili gs to gs
                            ay = float(data[5]) / 1000.0
                            az = float(data[6]) / 1000.0

                            #conver to meters per second squared
                            ax_converted = ax * G_TO_MS2
                            ay_converted = ay * G_TO_MS2
                            az_converted = az * G_TO_MS2 


                            self.ax = ax_converted
                            self.ay = ay_converted
                            self.az = az_converted - G_TO_MS2 

                            accel_vec = np.array([self.ax, self.ay, self.az])

                            self.accel_vec = accel_vec

                            print(self.accel_vec)


                            


                        if "C," in line:

                            data = line[2:].split(',')

                            timestamp = float(data[0]) / 1000

                            if self.prev_timestamp is None:
                                self.dt = 0 
                                self.prev_timestamp = timestamp


                            else:
                                self.dt = timestamp - self.prev_timestamp
                                self.prev_timestamp = timestamp

                            #in degrees
                            pitch = float(data[1])
                            roll = float(data[2])
                            yaw = float(data[3])

                            self.pitch = pitch
                            self.roll = roll 
                            self.yaw = yaw

                            euler_vec = np.array([self.yaw, self.pitch, self.roll])

                            self.euler_vec = euler_vec

                            print(self.euler_vec)




                    except Exception as e:
                        print(f"Invalid Sparton Data: {e}")

            except KeyboardInterrupt: 
                self.ser.write(b'0 accelp.p\r\n') #stop sending data
                self.ser.write(b'0 gyrop.p\r\n')
                self.ser.write(b'0 compass.p\r\n')
                print("closed")

                self.close()
   



    def close(self): 
        self.ser.write(b'0 accelp.p\r\n')
        self.ser.write(b'0 quat.p\r\n')
        self.ser.write(b'0 compass.p\r\n')
        self.ser.write(b'0 gyro.p\r\n')
        self.ser.close()




def main():
    
    
    t = SPARTON("/dev/tty.usbserial-FTG5PLPN")
   
    t.connect()
    t.enable_fusion_data()
    
    t.get_data_test()




    
    
if __name__ == '__main__':
    main()




