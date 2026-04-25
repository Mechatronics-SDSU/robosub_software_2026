import numpy as np
#from sparton import SPARTON 
from .trax_interface import Trax_Interface
from multiprocessing                        import Process, Value
import logging

# set up module level logger
LEVEL = logging.INFO
#logging.basicConfig(filename="packet_test4",level=logging.INFO)
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


class Node:
# TODO keep the acceleration due to gravity in this class to remove it as a last step
# Class responsible for abstracting each IMU node because the IMU's behave differently. Also provides data for testing and plotting.
	node_location = None # 4x4 describing position and orientation relative to center of mount/sub
	ID = None #IMU name
	measured_accel = None
	measured_wacc = None
	measured_wvel = None
 # 3x1 linear acceleration vectors corresponding to different nonzero relative accel. terms
	t_a_ci = None # This one is wdot cross ri
	t_a_di = None # This one is w^2 cross ri


	imu = None #sparton or trax interface object

	def __init__(self, shared_memory_object, ID, location):

		ZERO_VECTOR = np.zeros((3,1))

		self.node_location = location 
		self.ID = ID
        # keep a reference to shared memory for run_loop and imu access
		self.shared_memory_object = shared_memory_object
		#initialize each vector

		self.measured_accel = ZERO_VECTOR
		self.measured_wacc = ZERO_VECTOR
		self.measured_wvel = ZERO_VECTOR
		self.t_a_ci = ZERO_VECTOR
		self.t_a_di = ZERO_VECTOR

		

		'''
		TODO IMPLEMENT TRAX AND SPARTON DATA
		'''

		if self.ID == "SPARTON":
			self.imu = SPARTON()
			self.imu.enable_fusion_data()
			
		elif "TRAX" in self.ID:
			self.imu = Trax_Interface(shared_memory_object, False if self.ID == "TRAX1" else True, 1 if self.ID == "TRAX1" else 2)


	def print_data(self,string):
		self.log_string: str = string
		logger.info(self.log_string)

	def print_state(self) -> None:

		#function for centering print data. add two tabs
		def tprint(s) -> None: 
			print(f"\t\t{s}")

		#print location node in formatted rows
		def tprint_m(m) -> None:
			# accept lists or 1D arrays by converting to a 2D array
			try:
				arr = np.array(m)
				if arr.ndim == 0:
					tprint(arr)
					return
				if arr.ndim == 1:
					arr = arr.reshape(1, -1)
				for row in np.vsplit(arr, arr.shape[0]):
					tprint(row)
			except Exception:
				# fallback to simple print if reshaping fails
				tprint(m)

		tprint(f"=== NODE: {self.ID} ===")
		tprint("Location: ")
		tprint_m(self.node_location)

		vectors = {
				'measured_accel' : self.measured_accel,
				't_a_ci' : self.t_a_ci,
				't_a_di' : self.t_a_di
				}

		for key, value in vectors.items():
			if value is not None:
				value = value.T 
			tprint(f"--- {key} : {value}")

		print("")

	def run_loop(self)->None:
		self.imu.first_update()
		while self.shared_memory_object.running.value:
			match self.ID:
				case "SPARTON":
					print("SPARTON DATA NOT IMPLEMENTED YET")
				case "TRAX1":
					self.measured_accel=self.imu.get_data()
					try:
						self.shared_memory_object.trax_lin_acc[:] = self.measured_accel.reshape(-1) # store trax2 accel in shared memory
					except Exception as e:
						logger.critical(f"Error occurred while storing TRAX1 data: {e}")
				case "TRAX2":
					self.measured_accel, self.measured_wvel, self.measured_wacc = self.imu.get_data()
					try:
						# TODO could make angular velocity and accel a median of multuple recordings
						self.shared_memory_object.trax2_lin_acc[:] = self.measured_accel.reshape(-1) # store trax2 accel in shared memory
						self.shared_memory_object.trax2_ang_vel[:] = self.measured_wvel.reshape(-1) # store angular velocity in shared memory
						self.shared_memory_object.trax2_ang_acc[:] = self.measured_wacc.reshape(-1) # store angular acceleration in shared memory
					except Exception as e:
							logger.critical(f"Error occurred while storing TRAX2 data: {e}")
			#self.print_state()