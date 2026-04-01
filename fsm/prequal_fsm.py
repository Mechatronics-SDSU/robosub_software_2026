from utils.socket_send                      import set_screen
from fsm.fsm                                import FSM_Template
from enum                                   import Enum
import yaml, os

#first corner
#back
#second corner
#end/return point

class States(Enum):

	#enum values

	INIT = "INIT"
	DIVE = "DIVE" #dive to gate level
	FIRST_EDGE = "FIRST_EDGE" #go to first edge
	BACK = "BACK" #go to back of marker
	SECOND_EDGE = "SECOND_EDGE" #go to second edge
	END = "END" #go back to gate

	def __str__(self) -> str: #print state as string
		return self.value

class Prequal_FSM(FSM_Template):
	'''
	FSM for prequalification route around point - dive, go to first edge of point, circle around point, come back through gate
	'''

	def __init__(self, shared_memory_object, run_list: list):

		super().init(shared_memory_object, run_list)
		self.name: str = "PREQUAL"
		self.state: States = State.INIT

		self.x1 = self.x2 = self.x3 = self.x4 = self.y1 = self.y2 = self.y3 = self.y4 = self.x5 = self.y5 = self.gate_z = 0

		try:
			file = open("~/robosub_software_2026/objects.yaml", 'r')

			data = yaml.safe_load(file)

			#set target values
			course = data['course']
			self.x_buffer = data[course]['prequal']['x_buf']
			self.y_buffer = data[course]['prequal']['y_buf']
			self.x1 = data[course]['prequal']['x1']
			self.y1 = data[course]['prequal']['y1']
			self.x2 = data[course]['prequal']['x2']
			self.y2 = data[course]['prequal']['y2']
			self.x3 = data[course]['prequal']['x3']
			self.y3 = data[course]['prequal']['y3']
			self.x4 = data[course]['prequal']['x4']
			self.y4 = data[course]['prequal']['y4']
			self.x5 = data[course]['prequal']['x5']
			self.y5 = data[course]['prequal']['y5']
			self.gate_z = data[course]['prequal']['gate_z']


		except KeyError:
			print("ERROR: Invalid data format in objects.yaml, using all 0's")

	def start(self) -> None:
		#inherit start method from 
		super().start() #enables self.active
		self.next_state(START)

	def next_state(self, next: States) -> None:

		if not self.active or self.state == next: #if state didnt change just return 
			return
		else:
			match(next): #next state logic
				case States.INIT: 
					return
				case States.DIVE: #dive to gate level
					self.shared_memory_object.target_x.value = self.x1
                	self.shared_memory_object.target_y.value = self.y1
					self.shared_memory_object.target_z.value = self.gate_z
				case States.FIRST_EDGE: #set target values to first edge of route xy
					self.shared_memory_object.target_x.value = self.x2
					self.shared_memory_object.target_y.value = self.y2

				case States.BACK: #set target values to back of route xy
					self.shared_memory_object.target_x.value = self.x3
					self.shared_memory_object.target_y.value = self.y3

				case States.SECOND_EDGE: #set target values to second edge of route  xy
					self.shared_memory_object.target_x.value = self.x4
					self.shared_memory_object.target_y.value = self.y4

				case States.END: #set target values to starting point xy
					self.shared_memory_object.target_x.value = self.x5
					self.shared_memory_object.target_y.value = self.y5

				case _: #default for invalid state
					print(f"{self.name} INVALID STATE {self.state}")

			self.state = next
			print(f"{self.name}:{self.state}")

	def loop(self) -> None:

		if not self.active: #if not started return nothing
			return

		self.display(0,255,0) #update display rgb

		match(self.state): #transition between states
			case States.INIT:
				return
			case States.DIVE: #dive -> first edge
				if reached_xyz(self.x1, self.y1, self.gate_z):
					self.next_state(states.FIRST_EDGE)
			case States.FIRST_EDGE: #first_edge -> back
				if reached_xy(self.x2, self.y2):
					self.next_state(States.BACK)

			case States.BACK: #back -> second_edge
				if reached_xy(self.x3, self.y3):
					self.next_state(States.SECOND_EDGE)

			case States.SECOND_EDGE: #second_edge -> end
				if reached_xy(self.x4, self.y4):
					self.next_state(States.END)

			case States.END: #end -> suspend
				if reached_xy(self.x5, self.y5):
					self.suspend()

			case _:
				print(f"{self.name} INVALID STATE {self.state}")

