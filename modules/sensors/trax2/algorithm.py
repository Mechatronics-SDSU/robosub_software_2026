# File responsible for the model of the rigid body accelerometer test
# setup. 
# Needs to run on a run_loop to be used by FSM_Template.


import numpy as np
from node import Node
from utils import *

class Model:

    """ I am so glad I am not a programmer by trade """

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

        print("=== PRINTING MODEL ===")
        if flags is None:
            flags = self.__DEFAULT_PRINT_FLAGS

        def __upck(flag_name):
            # Check if flag_name is in flags, and if it
            # is true
            if (flag_name in flags) and (flags[flag_name] is True):
                return True
            return False

        if __upck('print_time'):
            print("\tlast_time: {}".format(self.last_time))

        if __upck('print_hist'):
            print("\taccel_hist: {}".format(self.accel_hist))
            print("\thist_idx: {}".format(self.hist_idx))

        if __upck('print_pos'):
            pdict = {'t_pos'  : self.t_pos,
                     't_tht'  : self.t_tht,
                     't_vel'  : self.t_vel,
                     't_wvel' : self.t_wvel,
                     't_acc'  : self.t_acc,
                     't_wacc' : self.t_wacc,
                     'm_pos'  : self.m_pos,
                     'm_acc'  : self.m_acc,
                     'm_vel'  : self.m_vel 
                     }

            for k, v in pdict.items():
                if v is not None:
                    v = v.T
                print("\t{} : {}".format(k, v))

        if __upck('print_tsfm'):
            print("\tcenter_T: \n{}".format(self.center_T))

        if __upck('print_nodes'):
            for node in self.nodes_list:
                node.print_state()

        print("======================")

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

    def step(self):
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

    def __init__(self, nodes, accel_hist, 
                 init_pos = np.zeros((3, 1)),
                 init_tht = np.zeros((3, 1)),
                 init_vel = np.zeros((3, 1)),
                 init_wvel = np.zeros((3, 1)),
                 fn_get_accel = None
                 ):
   
        # Initial conditions
        self.t_pos = init_pos
        self.t_tht = init_tht

        self.t_vel = init_vel
        self.t_wvel = init_wvel

        self.nodes_list = nodes
        self.center_T = np.zeros((4, 4))        # Initial position and orientation relative to global coordinates
        self.update_T()
        self.init_nodes()


        self.accel_hist = accel_hist
        self.hist_idx = 0
        self.last_time = 0

        # Initialize measurements to zero (No way to measure position, velocity
        # offset at start!)
        # TODO: ADDRESS THIS
        self.m_pos = np.zeros((3, 1))
        self.m_vel = np.zeros((3, 1))
        self.m_acc = np.zeros((3, 1))

        # Function to be used to get the acceleration at 
        # each timestep
        self.fn_get_accel = fn_get_accel



