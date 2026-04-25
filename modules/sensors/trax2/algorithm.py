# File responsible for the model of the rigid body accelerometer test
# setup. 
# Needs to run on a run_loop to be used by FSM_Template.


import numpy as np
from modules.sensors.trax2.node import Node
from utils import *
from multiprocessing                        import Process, Value
import time

class Model:

    """ I am so glad I am not a programmer by trade """

    trax1t_a_ci = None
    trax2t_a_ci = None
    trax1t_a_di = None
    trax2t_a_di = None
    node_pos_list = [] # just a temporary list of the node positions relative to the center (r_i)
    nodes_list = []         # All the nodes in the model from which measurement takes place

    center_T = None         # 4 x 4 transformation matrix representing the and orientation of the
                            # center of the model relative to the global coordinate system
    
    accel_hist = None       # File containing the acceleration of the center node in global coordinates at each timestep. 
                            # (dt, a_x, a_y, a_z, w*_x, w*_y, w*_z)

    hist_idx = None         # Keeps track of where in the acceleration history we are

    last_time = None

    t_pos = None              # 3x1 vector identifying the position of the center of the model in fixed-frame coordinates.
    t_tht = None            # 3x1 vector identifying the angular position of the center of the model in fixed-frame coordinates.

    t_vel = None              # 3x1 vector identifying the velocity of the center of the model in fixed-frame coordinates.
    t_wvel = None              # 3x1 vector identifying the angular velocity of the center of the model in fixed-frame coordinates.

    t_acc = None              # 3x1 vector identifying the accel. of the center of the model in fixed frame coordinates.
    t_wacc = None             # 3x1 vector identifying the angular accel. of the center of the model in fixed frame coordinates.

    m_pos = None            # Counterparts to the true 3x1 vectors above representing the attempted measurement of the
    m_acc = None            # acceleration vector, plus the double integration.
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
   
    fn_get_accel = None
    __CURR_TIME = 0

    def print_state(self, flags=None):
        def tprint(s) -> None:
            print(f"\t\t{s}")

        def tprint_m(m) -> None:
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
                tprint(m)

        # flags
        if flags is None:
            flags = self.__DEFAULT_PRINT_FLAGS

        def _flag(name: str) -> bool:
            return (name in flags) and flags[name]

        # ===== HEADER =====
        tprint("=== MODEL STATE ===")

        # ===== TIME =====
        if _flag('print_time'):
            tprint("Time: ")
            tprint(self.last_time)

        # ===== TRANSFORM =====
        if _flag('print_tsfm'):
            tprint("center_T: ")
            tprint_m(self.center_T)

        # ===== VECTORS (MATCH NODE STRUCTURE) =====
        if _flag('print_pos'):
            tprint("Vectors: ")

            vectors = {
                't_pos': self.t_pos,
                't_vel': self.t_vel,
                't_acc': self.t_acc,
                'm_pos': self.m_pos,
                'm_vel': self.m_vel,
                'm_acc': self.m_acc,
            }

            for key, value in vectors.items():
                tprint(f"--- {key} :")
                if value is not None:
                    try:
                        value = np.array(value).T
                    except Exception:
                        pass
                tprint_m(value)

        # ===== NODES =====
        if _flag('print_nodes'):
            for node in self.nodes_list:
                node.print_state()

        print("")

    
    def update_T(self):
        pos = self.t_pos.reshape(-1)
        tht = self.t_tht
        R_mat = mat_exp(tht)
        self.center_T[:3, :3] = R_mat
        self.center_T[:3, 3] = pos
        self.center_T[3, 3] = 1
        return

    def get_accel(self):
        if self.fn_get_accel is None:
            self.__CURR_TIME += 0.05
            lin_acc = np.zeros((3, 1))
            ang_acc = np.zeros((3, 1))
            return (self.__CURR_TIME, lin_acc, ang_acc)
    
        delta_t, lin_acc, ang_acc = self.fn_get_accel()
        self.__CURR_TIME += delta_t
        return (self.__CURR_TIME, lin_acc, ang_acc)
    

    def init_nodes(self):
        # Initialize the true and error positions for each
        # node
        center_rot, center_pos = unpack_T(self.center_T)
        for node in self.nodes_list:
            # TODO: THIS CODE IS REPEATED 3 PLACES, PUT INTO FUNCTION?
            node_R_b, node_pos_b = unpack_T(node.node_location)
            node_pos_s = center_rot @ (node_R_b.T @ node_pos_b)
            node.t_pos = self.t_pos + node_pos_s
            node.e_pos = node.t_pos

    def run_loop(self):
        while self.shared_memory_object.running.value:
            curr_time = time.time()
            delta_t = curr_time - self.last_time
            # TODO ask ryan about protection from reading from shared memory while its being written to 
            # temporarily just hard coding the step function to run for trax 1 and 2
            # multiprocessing.Array slices return lists; convert to numpy arrays before reshaping
            try:
                self.trax1_lin_acc = np.array(self.shared_memory_object.trax_lin_acc[:]).reshape((3, 1))
                self.trax2_lin_acc = np.array(self.shared_memory_object.trax2_lin_acc[:]).reshape((3, 1))
                self.ang_vel = np.array(self.shared_memory_object.trax2_ang_vel[:]).reshape((3, 1))
                self.ang_acc = np.array(self.shared_memory_object.trax2_ang_acc[:]).reshape((3, 1))

                # ensure 1-D length-3 arrays for cross product
                ang_acc_v = np.array(self.ang_acc).reshape(-1)
                ang_vel_v = np.array(self.ang_vel).reshape(-1)
                # TODO make angular velocity and this (r) are both in space or body frame (they must match)
                node0 = np.array(self.node_pos_list[0]).reshape(-1)
                node1 = np.array(self.node_pos_list[1]).reshape(-1)

                self.trax1t_a_ci = np.cross(ang_acc_v, node0).reshape(-1, 1)
                self.trax1t_a_di = np.cross(ang_vel_v, np.cross(ang_vel_v, node0)).reshape(-1, 1)

                self.trax2t_a_ci = np.cross(ang_acc_v, node1).reshape(-1, 1)
                self.trax2t_a_di = np.cross(ang_vel_v, np.cross(ang_vel_v, node1)).reshape(-1, 1)

                total_err = (self.trax1_lin_acc - (self.trax1t_a_ci + self.trax1t_a_di)) + (self.trax2_lin_acc - (self.trax2t_a_ci + self.trax2t_a_di))
                self.m_acc = total_err / 2
                self.m_vel += self.m_acc * delta_t
                self.m_pos += self.m_vel * delta_t
                self.print_state()
            except Exception as e:
                # shared memory may not be populated yet on first call; skip this iteration
                print(f"MODEL SKIPPING STEP (shared memory not ready or invalid shapes): {e}")
            time.sleep(0.05) # loop delay
        """
        # Flag-controlled breakpoint for debugging
        c_bp(_RUN_STATE)

        # Get the accelerations and timestep from the file
        curr_time, curr_accel_lin, curr_accel_ang = self.get_accel()
        delta_t = curr_time - self.last_time

        self.t_acc = curr_accel_lin
        self.t_wacc = curr_accel_ang

        # Calculate the update to the ground-truth velocity and position
        self.t_vel += delta_t * self.t_acc
        self.t_wvel += delta_t * self.t_wacc

        self.t_pos += delta_t * self.t_vel
        self.t_tht += delta_t * self.t_wvel
        self.update_T()
        center_rot, center_pos = unpack_T(self.center_T)
        
        # Calculate the ground-truth acceleration of each node
        for node in self.nodes_list:
  
            # Get the relative position vector represented in global coordinates.
            # Notably, this is not the same as the position of the node in global coordinates!
            node_R_b, node_pos_b = unpack_T(node.node_location)
           
            # Originally, I was against the use of A @ B as shorthand for np.matmul(A, B)
            # But it's really grown on me!
            node_pos_s = center_rot @ (node_R_b.T @ node_pos_b)

            # Relative acceleration terms
            node.t_a_ci = np.cross(
                    self.t_wacc.reshape(-1,),
                    node_pos_s.reshape(-1,)
                    ).reshape(-1, 1)

            node.t_a_di = np.cross(
                    self.t_wvel.reshape(-1,),
                    np.cross(self.t_wvel.reshape(-1,), node_pos_s.reshape(-1))
                    ).reshape(-1, 1)

            # Update the ground-truth acceleration vectors
            node.t_acc = self.t_acc + node.t_a_ci + node.t_a_di
            c_bp(_RUN_STATE)
            pass

        # Update the error position and velocity of the points
        # While you're at it, get the measured acceleration for the next part, too
        for node in self.nodes_list:
            node.m_acc = node.t_acc + node.e_acc
            node.e_vel += node.m_acc * delta_t
            node.e_pos += node.e_vel * delta_t

        # Prediction step - Figure out the best-fit acceleration of the center
        # and use that to update the predicted velocity and position
        total_err = np.zeros((3, 1))
        for node in self.nodes_list:
            total_err += (node.m_acc - (node.t_a_ci + node.t_a_di))

        self.m_acc = total_err / len(self.nodes_list)
        self.m_vel += self.m_acc * delta_t
        self.m_pos += self.m_vel * delta_t

        # Finally, update the predicted and true node positions in the space
        # frame. This makes logging easier.
        for node in self.nodes_list:
            node_R_b, node_pos_b = unpack_T(node.node_location)
            
            node_pos_s = center_rot @ (node_R_b.T @ node_pos_b)

            node.t_pos = self.t_pos + node_pos_s
            node.m_pos = self.m_pos + node_pos_s


        # Increment step count
        self.hist_idx += 1

        # Update last time
        self.last_time = curr_time

        return
        """

    def __init__(self, shared_memory_object, nodes_pos,  
                 init_pos = np.zeros((3, 1)),
                 init_tht = np.zeros((3, 1)),
                 init_vel = np.zeros((3, 1)),
                 init_wvel = np.zeros((3, 1)),
                 ):
   
        # Initial conditions
        self.t_pos = init_pos
        self.t_tht = init_tht

        self.t_vel = init_vel
        self.t_wvel = init_wvel
        self.node_pos_list.append(nodes_pos[0])
        self.node_pos_list.append(nodes_pos[1])
        self.last_time:    float = time.time()
        self.shared_memory_object = shared_memory_object

        #self.nodes_list = nodes
        self.center_T = np.zeros((4, 4))        # Initial position and orientation relative to global coordinates
        #self.update_T()
        #self.init_nodes()


        #self.accel_hist = accel_hist
        #self.hist_idx = 0
        #self.last_time = 0

        # Initialize measurements to zero (No way to measure position, velocity
        # offset at start!)
        # TODO: ADDRESS THIS
        self.m_pos = np.zeros((3, 1))
        self.m_vel = np.zeros((3, 1))
        self.m_acc = np.zeros((3, 1))

        # Function to be used to get the acceleration at 
        # each timestep
        #self.fn_get_accel = fn_get_accel



