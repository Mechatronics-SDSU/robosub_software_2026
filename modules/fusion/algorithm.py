import numpy as np 
import time
from multiprocessing import Process, Manager
from sparton_fusion_data import SPARTON_FUSION
#from trax_interface import Trax_Interface

'''

    given time step: predicted position, velocity, acceleariton in space frame, , euler angle vector, angular velocity vector, angular acceleration vector
    k means certain time step

    NOTHING AT NODE LEVEL

    for given time step: 
    1.have euler angle vector
    2.compute R(euler) and T(euler)

    3. compute angular velocity: R(euler) @ T(euler) @ gyro
    4. compute angular accel space frame: wk - w(k-1) / delta t    (angualr vleocity - prev anulgar velocity)
        body frame angular_velocity: Rotation matrix.Tranpose(euler) * angular velocity space frame
        body frame anguarl_accel = Rotation matrix.Transpoe(euler) * angular_accel in space fame

    5. compute MODEL accleeration in body frame: 1/n * sum (node's accel np.cross(angular_vel, np.cross(angular_ve, distance_from_roign_node)) + np.cross(angular_accel, distance_from_node))
    doing each per node for the sum
    all values in body frame??

    6. model accelereaton in space frame: Rotation(euler) @ model acceleraiton in body

    7. model velocity in space frame = previous_vel_space + change_in_time_*accel_space

    8. model positon = prev_pos_space + changein_time*vel_space
    

    --NOTES----------------------------------------------
    INITIAL CONDITIONS: start sub, starting position = prev_pos_space = 0, vel,accel = 0, eulers = 0


    g_vector = [0,0,-9.8]
    g_vector_in_body = R.T(euler)*g_vector

    try subtracting at start when pulling sensor data, or at end test both
    subtract at end before model accelreation -> velocity integration if doing end
    ALWAYS USE @ wherever R or T matrix is


    ---IF NONE  OF THIS WORKS, DO IT FOR ONE IMU ------

'''



    
def sensor_process(shared_data):

	sensor = SPARTON_FUSION("/dev/tty.usbserial-FTG5PLPN")
	sensor.connect()
	sensor.enable_fusion_data()
	sensor.get_data(shared_data)


class Fusion:

	def __init__(self, test=None, limit=None, test_accel=None):

		self.test = test
		
		self.test_accel = test_accel 


		self.R = None # rotation matrix for turning acceleration from body to space frame
		self.T_matrix = None #transformation matrix
		self.euler_angles = np.zeros(3)
		self.gyro_vector = np.zeros(3)
		self.imu_accel_linear = np.zeros(3)

		self.t_prev = 0

		self.g_vector = [0,0,-9.8]
		self.g_vector_body = None

		self.ang_vel_space = np.zeros(3)
		self.ang_vel_body = np.zeros(3)

		self.ang_accel_space = np.zeros(3)
		self.ang_accel_body = np.zeros(3)

		self.imu_accel_linear = None

		self.model_accel_body = None
		self.model_accel_space = None
		self.model_vel_space = None
		self.model_pos_space = None

		self.dt  = 0 #time since previous sensor pull I guess

		#variables to store previous vals

		self.prev_wvel_space = np.zeros(3)
		self.prev_vel_space = np.zeros(3)
		self.prev_pos_space = np.zeros(3)

		self.CURRENT_TIME = 0
		self.limit = limit
		self.t_prev = None


		self.DISTANCE_FROM_CENTER = .10795 #measured from my test model board. this will change depending on the subs dimensions


	def get_sensor(self):
		self.manager = Manager()
		self.shared_data = self.manager.dict()


		self.p = Process(target=sensor_process, args=(self.shared_data,))

		self.p.start()

		

	
	def run_loop(self):


		#1.have euler angle vector, gyro vector, and dt - shared across all because moving the same and they dont have disecprencies between them for this data
		try:
			while self.CURRENT_TIME <= self.limit:
				
				
				
				if self.test == True:

					self.imu_accel_linear = [self.test_accel, self.test_accel, self.test_accel]
					self.euler_angles = np.array([0, 0.0, .0]) # yaw pitch roll
					self.gyro_vector = np.array([0.0, 0.0, 0.0])
					dt = .003
					self.CURRENT_TIME += dt

				else:
					self.gyro_vector = self.shared_data.get("gyro_vec")
					self.euler_angles = self.shared_data.get("euler_vec")
					self.imu_accel_linear = self.shared_data.get("accel_vec")
					dt = self.shared_data.get("dt")
					print(dt)
					self.CURRENT_TIME += dt
					
					
					


				cy = np.cos(float(self.euler_angles[0])) #cos(yaw)
				cp = np.cos(float(self.euler_angles[1])) #cos(pitch)
				cr = np.cos(float(self.euler_angles[2])) #cos(roll)
				
				sy = np.sin(float(self.euler_angles[0])) #sin(yaw)
				sp = np.sin(float(self.euler_angles[1])) #sin(pitch)
				sr = np.sin(float(self.euler_angles[2])) #sin(roll)
				

				ty = np.tan(float(self.euler_angles[0])) #tan(yaw)
				tp = np.tan(float(self.euler_angles[1])) #tan(pitch)
				tr = np.tan(float(self.euler_angles[2])) #tan(roll)

				#roll = phi (circle line)
				#yaw = psi (fork)
				#pitch = theta 

				#2.compute R(euler) and T(euler)
				self.T_matrix = np.array([
				[ 1,                    sr * tp,             cr * tp],
				[ 0,                	cr,             		 -sr],
				[ 0,             		sr / cp,             cr / cp]
				])

				self.R = np.array([ 
				[ cy*cp,  cy*sp*sr - sy*cr,  cy*sp*cr + sy*sr ],
				[ sy*cp,  sy*sp*sr + cy*cr,  sy*sp*cr - cy*sr ],
				[   -sp,             cp*sr,              cp*cr ]
				])


				#self.g_vector_body = self.R.T @ self.g_vector

				#self.imu_accel_linear = self.imu_accel_linear - self.g_vector_body


				#3. compute angular velocity: R(euler) @ T(euler) @ gyro
				self.ang_vel_space = self.R @ self.T_matrix @ self.gyro_vector

				#4. compute angular accel space frame: wk - w(k-1) / delta t    (angualr vleocity - prev anulgar velocity)
				self.ang_accel_space = (self.ang_vel_space - self.prev_wvel_space) / dt

				
				self.prev_wvel_space = self.ang_vel_space

				


				#	body frame angular_velocity: Rotation matrix.Tranpose(euler) * angular velocity space frame
		        #	body frame anguarl_accel = Rotation matrix.Transpoe(euler) * angular_accel in space fame
				self.ang_vel_body = self.R.T @ self.ang_vel_space
				self.ang_accel_body = self.R.T @ self.ang_accel_space


				
				#    5. compute MODEL accleeration in body frame: 
				#	1/n * sum (node's accel - np.cross(angular_vel, np.cross(angular_ve, distance_from_roign_node)) + np.cross(angular_accel, distance_from_node))
				accel_sum = np.zeros(3) # i think this is 3x1 array
				if self.test == True:
					for i in range(1):
						accel_sum += (self.imu_accel_linear[i] - (np.cross(self.ang_vel_body, np.cross(self.ang_vel_body, np.array([self.DISTANCE_FROM_CENTER, 0.0, 0.0]))) 
															+ np.cross(self.ang_accel_body, np.array([self.DISTANCE_FROM_CENTER, 0.0, 0.0]))))
					self.model_accel_body = accel_sum / 1
				else:
					accel_sum += (self.imu_accel_linear - (np.cross(self.ang_vel_body, np.cross(self.ang_vel_body, np.array([self.DISTANCE_FROM_CENTER, 0.0, 0.0]))) 
															+ np.cross(self.ang_accel_body, np.array([self.DISTANCE_FROM_CENTER, 0.0, 0.0]))))
					
					self.model_accel_body = accel_sum

			

				#6. model accelereaton in space frame: Rotation(euler) @ model acceleraiton in body
				self.model_accel_space = self.R @ self.model_accel_body

				#subtract at gravity vector end before model accelreation -> velocity integration if doing end 
				#DOUBLE CHECK WHETHER TO USE G_VECTOR OR G_BODY_VECTOR
				#self.model_accel_space = self.model_accel_space - self.g_vector_body

				#7. model velocity in space frame = previous_vel_space + change_in_time_*accel_space
				self.model_vel_space = self.prev_vel_space + (dt * self.model_accel_space)

				#8. model positon = prev_pos_space + changein_time*vel_space
				self.model_pos_space = self.prev_pos_space + (dt * self.model_vel_space)

				self.prev_pos_space = self.model_pos_space
				self.prev_vel_space = self.model_vel_space


				
				#print(self.model_pos_space)
				

				#boom self.model_pos_space is   good for model

			if self.test == False:
				self.p.terminate()
				self.p.join()

		except KeyboardInterrupt:
			print("closing")
			self.p2.join()


    
	

def main():
	t = True
	test = Fusion(t)
	
	test.get_sensor()
	
	time.sleep(2)

	test.run_loop()




	
if __name__ == '__main__':
	main()
	




