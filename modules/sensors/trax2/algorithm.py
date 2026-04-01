import numpy as np 
from node import Node
from utils import *
from sparton import SPARTON

class Model:

	# t = ground truth

	nodes_list = [] #all nodes/IMUs

	center_T = None #4x4 transformation matrix representing center of model

	accel_history = None #(dt, a_x, a_y, a_z, w*_x, w*_y, w*_z) at each timestep

	history_idx = None #where in history current we are

	last_timestep = None

	t_pos = None # 3x1 vector identifying the position of the center of the model in fixed-frame coordinates.
	t_theta = None # 3x1 vector identifying the angular position of the center of the model in fixed-frame coordinates.

	t_vel = None
	t_wvel = None #w = angular

	t_acc = None #true accel / angular accel
	t_wacc = None

	m_pos = None #measured vals
	m_acc = None
	m_vel = None


	_ALL_PRINT_FLAGS = {
	        		"print_time" : True,
	        		"print_hist" : True,
	        		"print_nodes" : True,
	        		"print_pos" : True,
	        		"print_tsfm" : True
	        		}

	__DEFAULT_PRINT_FLAGS = {
	        		"print_time" : False,
	        		"print_hist" : False,
	        		"print_nodes" : False,
	        		"print_pos" : True,
	        		"print_tsfm" : True
	        		} 

	accel_function = None
	CURRENT_TIME = 0

	def __init__(self, nodes, accel_hist, init_pos = np.zeros((3,1)), init_tht = np.zeros((3,1)), init_vel = np.zeros((3,1)), init_wvel = np.zeros((3,1)), accel_fn = None):

		#initial conditions
		self.t_pos = init_pos
		self.t_theta = init_tht

		self.t_vel = init_vel
		self.t_wvel = init_wvel 

		self.nodes_list = nodes 
		self.center_T = np.zeros((4, 4)) #initial position and orientation in global frame
		self.update_T()
		self.init_nodes()

		self.accel_history = accel_hist 
		self.history_idx = 0
		self.last_timestep = 0

		#initiliaze measurements to zero
		self.m_pos = np.zeros((3,1))
		self.m_vel = np.zeros((3,1))
		self.m_acc = np.zeros((3,1))

		self.accel_function = accel_fn #check if accel function is created

	def print_state(self, flags=None) ->None:
		if flags is None:
			flags = self.__DEFAULT_PRINT_FLAGS

		def __upck(flag_name) ->bool:

			if (flag_name in flags) and (flags[flag_name]): #add true if failing
				return True
			return False

		if __upck('print_time'):
			print(f"\tlast_time: {self.last_timestep}")

		if __upck('print_hist'):
			print(f"\taccel_hist: {self.accel_history}")
			print(f"\thist_idex: {self.history_idx}")

		if __upck('print_pos'): #print all the different variables

			variables = {'t_pos'  : self.t_pos,
                     't_theta'  : self.t_theta,
                     't_vel'  : self.t_vel,
                     't_wvel' : self.t_wvel,
                     't_acc'  : self.t_acc,
                     't_wacc' : self.t_wacc,
                     'm_pos'  : self.m_pos,
                     'm_acc'  : self.m_acc,
                     'm_vel'  : self.m_vel
                     }

		for key, val in variables.items():
		    	if val is not None:
		    		val = val.T 

		    	print(f"\t{key} : {val}")
		if __upck('print_tsfm'):
			print(f"\tcenter_T: \n{self.center_T}")

		if __upck('print_nodes'): #print flag for all nodes
			for node in self.nodes_list:
				node.print_state()

			print("======================")


	def update_T(self) -> None:
		pos = self.t_pos.reshape(-1) #flatten to 1D
		theta = self.t_theta
		rotation_matrix = mat_exp(theta)
		self.center_T[:3, :3] = rotation_matrix
		self.center_T[:3, 3] = pos 
		self.center_T[3, 3] = 1

	 

	def get_accel(self) ->tuple:
		if self.fn_get_accel is None: #if fn_get_accel() isn't declared?
			self.CURRENT_TIME += 0.05
			linear_accel = np.zeros((3, 1))
			angular_accel = np.zeros((3, 1))
			return (self.CURRENT_TIME, linear_accel, angular_accel)

		dt, linear_accel, angular_accel = self.fn_get_accel() #3x1 matrices for linear/angular accel
		self.CURRENT_TIME += dt 
		return (self.CURRENT_TIME, linear_accel, angular_accel)


	'''
	NEEDS TO BE TESTED AND FIXED WHEN WE MEET
	'''
	
	def fn_get_accel(self):  #function for getting data from each imu 
		total_time, total_lin, total_ang = 0
		
		for node in self.nodes_list: #get timestep, lin/ang accel from sparton
			if node.ID == "SPARTON":
				time, lin_acc, ang_acc = node.imu.get_data()

			elif node.ID == "TRAX": #I dont know how ang_acc will work for trax so this might need fixing
				lin_acc, ang_acc = node.imu.get_data() #full of bugs 
				

			total_lin += lin_acc
			total_ang += ang_acc 

		#used for getting the data for model not single IMU (for now). not the final solution
		acc = total_line / len(self.nodes_list)
		wacc = total_ang / len(self.nodes_list)

		return time, acc, wacc

		
		

	def init_nodes(self) ->None:
		#initialize true and error position for each node

		center_angles, center_xyz = unpack_T(self.center_T)

		for node in self.nodes_list:
			#find out what _b means later
		

			node_angles_b, node_position_b = unpack_T(node.node_location)
			node_pos_s = center_angles @ (node_angles_b.T @ node_position_b)
			node.t_pos = self.t_pos + node_pos_s 
			node.e_pos = node.t_pos 

	def step(self) ->None:

		curr_time, curr_accel_lin, curr_accel_ang = self.get_accel()
		dt = curr_time - self.last_timestep

		self.t_acc = curr_accel_lin
		self.t_wacc = curr_accel_ang 

		#update ground-truth velocity and position
		self.t_vel += dt * self.t_acc 
		self.t_wvel += dt * self.t_wvel

		self.t_pos += dt * self.t_vel 
		self.t_theta += dt * self.t_wvel 
		self.update_T()

		center_angles, center_xyz = unpack_T(self.center_T) #get angles and position again AFTER updating

		for node in self.nodes_list:
			node_angles_b, node_position_b = unpack_T(node.node_location)

			node_pos_s = center_angles @ (node_angles_b.T @ node_position_b)

			#relative acceleartion

			node.t_a_ci = np.cross(self.t_wacc.reshape(-1,), node_pos_s.reshape(-1,)).reshape(-1,1)

			node.t_a_di = np.cross(self.t_wvel.reshape(-1,), node_pos_s.reshape(-1,)).reshape(-1,1)

			node.t_acc = self.t_acc + node.t_a_ci + node.t_a_di  #update ground-truth accel vectors

		#update error position, velocity, and measured accel of the IMUs
		for node in self.nodes_list:
			node.measured_accel = node.true_accel + node.error_accel
			node.error_vel += node.measured_accel * dt 
			node.error_pos += node.erro_vel * dt 

		#find best fit acceleration of center and use to update predicted vel/pos
		total_error = np.zeros((3,1))

		for node in self.nodes_list:
			total_error += (node.measured_accel - (node.t_a_ci + node.t_a_di)) #matrix addition

		self.m_acc = total_error / len(self.nodes_list) #error / total IMUs
		self.m_vel += self.m_acc * dt
		self.m_pos += self.m_vel * dt

		#update predicted and true IMU positions in space
		for node in self.nodes_list:
			node_angles_b, node_position_b = unpack_T(node.node_location) #angles_b is 3x3 rotation matrix, pos_b 3x1 position matrix
			node_position_s = center_angles @ (node_angles_b.T @ node_position_b)

			node.true_pos = self.t_pos + node_position_s
			node.m_pos = self.m_pos + node_position_s  

		self.history_idx += 1

		self.last_timestep = curr_time 


 















