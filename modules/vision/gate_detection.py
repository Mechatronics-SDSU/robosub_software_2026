import time
import cv2
import numpy        as np

"""
    discord: @kialli
    github: @kchan5071

    Detects robosub gate, drives towards it after confidence threshold

"""

def downsample_image(image, block_size, min_depth, max_depth):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width, _ = image.shape
    x_scaling = width / block_size
    y_scaling = height / block_size
    down_sized = cv2.resize(gray, (0, 0), fx = 1 / x_scaling, fy = 1 / y_scaling, interpolation=cv2.INTER_AREA)
    upsized = cv2.resize(down_sized, (0, 0), fx = x_scaling, fy = y_scaling, interpolation=cv2.INTER_AREA)
    _, filter_too_close = cv2.threshold(upsized, min_depth, 255, cv2.THRESH_TOZERO_INV) #2nd param, higher means closer, mi
    _, middle_thresh = cv2.threshold(filter_too_close, max_depth, 255, cv2.THRESH_BINARY) #2nd param, higher means closer, minimum cutoff
    return middle_thresh

def get_rid_of_max_consecutives(pixel_list, max_consecutives):
    #if there are more than max_consecutives in a row, get rid of them(set them to 0)
    consecutives = 0
    start_of_consecutives = 0
    for i in range(len(pixel_list)):
        if pixel_list[i] != 1 and i < len(pixel_list) - 1:
            consecutives = 0
            start_of_consecutives = i + 1
            continue
        else:
            consecutives += 1
            if consecutives == max_consecutives:
                for j in range(start_of_consecutives, i + 1):
                    pixel_list[j] = 0
                consecutives = 0
    return pixel_list

def fill_small_gaps(pixel_list, min_gap):
    gap = 0
    start_of_gap = 0
    for i in range(len(pixel_list)):
        if pixel_list[i] == 1:
            if i > 1 and gap > 0 and gap <= min_gap: # if a valid gap of empties (not at the start) is bookended by a 1:
                for j in range(start_of_gap, i + 1): # go through the gap and make them 1s
                    pixel_list[j] = 1
            gap = 0  # set gap to 0
            start_of_gap = i + 1 # start of gap is index + 1
        else: # if pixel is a 0
            gap += 1
    return pixel_list

def weighted_cluster_position_average(array, wgt, width_in_pixels):
    """
        weighton larmer
    """
    size = len(array)
    wgt_sum = 0
    half = width_in_pixels / 2

    if (size == 0): # return 0 as invalid number code if there is no gate IDs
        return 0 
    else:
        for i in range(size): # iterate through each item in array
            wgt_sum += int(half) + wgt * (array[i] - half) # add weighter value to sum
        return int(wgt_sum/size) # return weighted avg 
# when calling this, make the second parameter (weight) a decimal just below 1.0

def average_cluster_positions(pixel_list):
    #cluster is defined as a group of 1s
    cluster_positions = []
    cluster = []
    for i in range(len(pixel_list)):
        if pixel_list[i] == 1:
            cluster.append(i)
        else:
            if cluster:
                cluster_positions.append(np.average(cluster))
                print("Cluster: ", cluster)
                print("AVG:", np.average(cluster))
                cluster = []
    return cluster_positions

def correct_equator(image, pitch):
    print("Pitch: ", pitch)
    #not using weight
    height, _ = image.shape
    middle = height // 2 # 240 pixels
    #estimated yaw to pixel offset ratio
    Lratio = height
    pitch_offset = pitch * Lratio
    if pitch_offset >= 0:
        pitch_offset = min(pitch_offset, height * .2)
    else:
        pitch_offset = max(pitch_offset, height * -.2)
    new_middle = int(middle + pitch_offset)
    middle_pixels = image[new_middle]
    middle_flat = np.array(middle_pixels).flatten()
    middle_clipped = np.clip(middle_flat, 0, 1)
    return middle_clipped, pitch_offset

def find_equator(image, _):
    #not using weight
    height, _ = image.shape
    # find center
    middle = height // 2
    middle_pixels = image[middle]
    middle_flat = np.array(middle_pixels).flatten()
    middle_clipped = np.clip(middle_flat, 0, 1)
    return middle_clipped, 0

def count_changes(pixel_list):
    changes = 0
    position = 0
    for i in range(1, len(pixel_list)):
        if positive_to_negative_change(pixel_list[i], pixel_list[i - 1]):
            changes += 1
            position += i
    if changes <= 1 or changes % 2 == 1:
        return 0
    return position / changes

def positive_to_negative_change(num1, num2):
    return num1 - num2 == 1


NUM_OFFSET = 20
ABS_MAX_OFFSET = 100

class CheckValid:
    valid_offsets = 0
    misses = 0
    def storing_frames(self, x_offset):
        x_offset = abs(x_offset)
        if x_offset != 0:
            self.valid_offsets += 1
            if self.valid_offsets >= NUM_OFFSET:
                return True
            return False
        else:
            self.misses += 1
            if self.misses >= 5:
                self.valid_offsets = 0
                self.misses = 0
            return False
        
def show_clusters(image, x, valid: bool, pitch_offset):
    height, width, _    = image.shape
    middle_y            = height // 2
    middle_x            = width // 2
    color               = (255, 0, 0) if valid else (0, 0, 255)
    return cv2.circle(img=image, center=(int(x), int(middle_y + pitch_offset)), radius= 7, color=color, thickness=2)

def show_offset(image, x, valid: bool, pitch_offset):
    height, width, _    = image.shape
    middle_y            = height // 2
    middle_x            = width // 2
    color               = (255, 100, 0) if valid else (0, 255, 0)
    return cv2.circle(img=image, center=(int(x), int(middle_y + pitch_offset)), radius= 15, color=color, thickness=3)
