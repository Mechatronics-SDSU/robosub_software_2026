import numpy as np
from sparton import SPARTON 
from trax_interface import Trax_Interface


class Node:

	   # Class responsible for representing each IMU in model 

	node_location = None # 4x4 describing position and orientation relative to center of mount/sub

	ID = None #IMU name

	true_pos = None  # 3x1 vector describing the position of the node in global coordinates
	measured_pos = None

	error_pos = None # 3x1 vectors for position and velocity from integration
	error_vel = None

	measured_vel = None 
	true_vel = None

	true_accel = None # linear acceleration in global coordinates
	error_accel = None # error vector from integration?
	measured_accel = None # M = T + E

	t_a_ci = None # 3x1 linear acceleration vectors corresponding to different nonzero relative accel. terms
	t_a_di = None 


	imu = None #sparton or trax

	def __init__(self, location, error_vector, ID):

		ZERO_VECTOR = np.zeros((3,1))

		#initialize each vector, grouped by variable


		self.true_pos = ZERO_VECTOR
		self.measured_pos = ZERO_VECTOR

		self.true_vel = ZERO_VECTOR
		self.measured_vel = ZERO_VECTOR

		self.true_accel = ZERO_VECTOR	
		self.measured_accel = ZERO_VECTOR

		self.error_pos = ZERO_VECTOR
		self.error_vel = ZERO_VECTOR
		self.error_accel = error_vector #TODO get error_vector of sparton for testing

		self.t_a_ci = ZERO_VECTOR
		self.t_a_di = ZERO_VECTOR

		self.node_location = location 
		self.ID = ID

		'''
		TODO IMPLEMENT TRAX AND SPARTON DATA
		'''

		if self.ID == "SPARTON":
			self.imu = SPARTON()
			self.imu.enable_fusion_data()
			
		elif self.ID == "TRAX":
			self.imu == trax_interface()
			self.imu.setup()



	def print_state(self) -> None:

		#function for centering print data. add two tabs
		def tprint(s) -> None: 
			print(f"\t\t{s}")

		#print location node in formatted rows
		def tprint_m(m) -> None:
			for row in np.vsplit(m, np.shape(m)[0]):
				tprint(row)

		tprint(f"=== NODE: {self.ID} ===")
		tprint("Location: ")
		tprint_m(self.node_location)

		vectors = {
				'true_pos' : self.true_pos,
				'measured_pos' : self.measured_pos,
				'true_accel' : self.true_accel,
				'measured_accel' : self.measured_accel,
				'error_pos' : self.error_pos,
				'error_vel' : self.error_vel,
				'error_accel' : self.error_accel,
				't_a_ci' : self.t_a_ci,
				't_a_di' : self.t_a_di
				}

		for key, value in vectors.items():
			if value is not None:
				value = value.T 
			tprint(f"--- {key} : {value}")

		print("")

