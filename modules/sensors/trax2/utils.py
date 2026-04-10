import numpy as np

### ===== PDB UTILITY      ===== ###

from enum import Enum
class RUN_STATE(Enum):
    NORMAL = 1000
    TEST = 1001


def c_bp(cond):
    if cond == RUN_STATE.TEST:
        breakpoint()

### ===== MATH UTILITY     ===== ###

def pack_T(pos, rot):
    tsfm = np.zeros((4, 4)) #might be able to just use 3x3
    tsfm[:3, :3] = rot
    tsfm[:3, 3] = pos
    tsfm[3, 3] = 1
    return tsfm
    

def unpack_T(T_mat):
    rot = T_mat[:3, :3] #first 3 columns of first 3 rows 3x3 matrix
    pos = T_mat[:3, 3].reshape(-1, 1) #3rd column of first 3 rows (indexing starts at 0)
    return (rot, pos)

def to_skew_symm(w_vec):
    # Helper responsible for returning the skew-symmetric rep.
    # of a vector
    w_vec = w_vec.reshape(-1)
    w_1 = w_vec[0]
    w_2 = w_vec[1]
    w_3 = w_vec[2]
    ret = np.array([[0,    -w_3,  w_2], 
                    [w_3,  0,    -w_1],
                    [-w_2, w_1,    0]])

    return ret

def from_skew_symm(w_mat):
    # Helper responsible for recovering the axial vector from
    # a skew-symmetric matrix
    w_vec = np.zeros((3,))
    w_vec[0] = w_mat[2, 1]
    w_vec[1] = w_mat[0, 2]
    w_vec[2] = w_mat[1, 0]
    w_vec = w_vec.reshape(-1, 1)
    return w_vec


    
