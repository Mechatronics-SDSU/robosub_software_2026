import modules.vision.Yolov5Detection                           as yv5
import modules.vision.Socket_Client                             as Socket_Client
import modules.vision.gui_helper                                as gui_helper
import modules.vision.gate_detection                            as gate_detection

from modules.vision.ColorFilter.color_filter                    import ColorFilter
from modules.vision.ColorFilter.color_filter_config_parser      import Color_Config_Parser
from modules.vision.gate_detection                              import CheckValid

import math
import cv2
import multiprocessing
import time
from multiprocessing                                    import Value
import numpy                                            as np



#-----------------------------testing for zed sdk-------------------------
import_success = True
try:
    import pyzed.sl                                     as sl 
    from modules.vision.Zed_Wrapper                             import Zed
except:
    print("Zed library not found")
    import_success = False
#-------------------------------------------------------------------------

class VideoRunner:
    """
    discord: @kialli
    github: @kchan5071
    
    main class to run vision code
    
    usage:
    initialize class
    run loop
    """

    def __init__(self,  shared_memory_object, hard_deadzone):
        """
            initializes class
            input
                shared_memory_object: SharedMemoryWrapper object

        """

        self.shared_memory_object = shared_memory_object

        self.hard_deadzone = (hard_deadzone - 1) / 2


        self.color_filter = ColorFilter()

        self.model_path = './models_folder/yolov5m.pt'
        
        
        self.detection = None
        self.skip_frames = 0
        self.frame_count = self.skip_frames

        self.validated = False
        self.locked = False

    def get_nearest_object(self, results):
        """
            gets distance of the nearest object from the bounding boxes
            input
                results: yolov5 results object
            return
                nearest_object_distance: float
                nearest_box: np_array
        """
        nearest_object_distance = math.inf
        nearest_box = None
        for box in results.xyxy[0]:
            if box[5] != 0:
                continue

            median = self.zed.get_median_distance(int(box[0]), int(box[1]), int(box[2]), int(box[3]))
            if not math.isnan(median) and not math.isinf(median) and not median <= 0:
                nearest_object_distance = min(median, nearest_object_distance)
                nearest_box = box
                
        return nearest_object_distance, nearest_box
    
    def enable_color_filter(self):
        self.shared_memory_object.color_enable = True

    def set_color_filter(self, color_filter):
        self.color_filter = color_filter

    def get_yolo_offset(self, box, results, image):
        """
            gets distance from the center of the nearest object to the center of the image
            input
                box: np_array
                results: yolov5 results object
                image: np_array
            return
                yolo_offset_x: int
                yolo_offset_y: int
        """
        if (box is None):
            return 0, 0
        
        center_x = image.shape[1] // 2
        center_y = image.shape[0] // 2
        
        xB = int(box[2])
        xA = int(box[0])
        yB = int(box[3])
        yA = int(box[1])
        object_center_x = (xB + xA) / 2
        object_center_y = (yB + yA) / 2
        
        yolo_offset_x = center_x - object_center_x
        yolo_offset_y = center_y - object_center_y
        
        return yolo_offset_x, yolo_offset_y
        
    def create_camera_object(self):
        """
            creates camera objects
            if zed is successful in opening and importing, it will use zed
            otherwise it will use cv2.VideoCapture(0)

            one of the returned objects will be None

            return
                zed: zed object
                cap: cv2.VideoCapture
        """
        self.zed = None
        self.cap = None
        #import success tests if zed sdk imported successfully
        if import_success:
            self.zed = Zed()
            state = self.zed.open()
            if state != sl.ERROR_CODE.SUCCESS:
                self.zed = None
                print("Zed camera not found, using webcam")
                self.cap = cv2.VideoCapture(0)
        else:
            self.zed = None
            print("camera library not found, using webcam")
            self.cap = cv2.VideoCapture(0)

    def send_image_to_socket(self, socket, image):
        """
            sends image to socket
            input
                socket: Socket_Client object
                image: np_array
        """
        try:
            socket.send_video(image)
        except Exception as e:
            print(e)
            socket.client_socket.close()

    def get_image(self):
        """
            gets image from camera
            if zed is not None, it will get image from zed
            if cap is not None, it will get image from cap
            prefers to use zed

            input
                zed: zed object
                cap: cv2.VideoCapture

            return
                image: np_array
        """
        if self.zed is not None:
            image = self.zed.get_image()
            return image
        if self.cap is not None:
            _, image = self.cap.read()
            return image
        else:
            print("No camera found, exiting")
            return None

    def swap_model(self, model_path):
        """
            swaps model in detection object
            placeholder function in case this gets harded in the future

            input
                model_path: path to new model
        """
        self.detection.load_new_model(model_path)

    def share_imu_to_shared_memory(self):
        """
            gets zed imu data and shares it to shared memory

            doesnt really belong in this process, but the zed camera can only have one instance

            TO DO: move this to a separate process
        """
        orientation, lin_acc, ang_vel = self.zed.get_imu()
        
        #set shared memory values
        self.shared_memory_object.imu_lin_acc = lin_acc
        self.shared_memory_object.imu_ang_vel = ang_vel
        self.shared_memory_object.imu_orientation = orientation

        self.shared_memory_object.linear_acc[1] -= 9.8

    def connect_to_server():
        """
            testing function to connect to server
            used for sending images to host for viewing

            return 
                socket: Socket_Client object
        """
        host = '192.168.194.3'
        port = 8991
        socket = Socket_Client.Client(host, port)
        socket.connect_to_server()
        return socket
    
    def run_yolo_detection(self, show_boxes, image):
        """
            runs yolo detection on image
            if show_boxes is set to True, it will draw bounding boxes
            input
                show_boxes: bool
                image: np_array
            return
                image: np_array
        """
        #run yolo detection
        results = None
        if (self.frame_count >= self.skip_frames):
            results = self.detection.detect_in_image(image)
            self.frame_count = 0
        else:
            self.frame_count += 1
        if show_boxes:
            image = gui_helper.draw_boxes(image, results)
            image = gui_helper.draw_lines(image, results)

        #get distance of nearest object(set to True by default)     
        if self.zed is not None:
            distance, box = self.get_nearest_object(results)
            yolo_offset_x, yolo_offset_y= self.get_yolo_offset(box, results, image)
            self.shared_memory_object.yolo_offset[0] = yolo_offset_x
            self.shared_memory_object.yolo_offset[1] = yolo_offset_y
            self.shared_memory_object.distance_from_object.value = float(distance)
        return image
    
    def run_color_detection(self, image, color):
        """
            runs color detection on image
            input
                image: np_array
                color: int
            return
                image: np_array
        """
        
        #self.color_filter.set_color_target(color)
        image, position = self.color_filter.auto_average_position(image)
        if position is None:
            self.shared_memory_object.color_offset[0] = 0.0
            self.shared_memory_object.color_offset[1] = 0.0
            return image
        self.shared_memory_object.color_offset[0] = position[0] - image.shape[1] // 2
        self.shared_memory_object.color_offset[1] = position[1] - image.shape[0] // 2
        if self.zed is not None:
            self.shared_memory_object.distance_from_object.value = self.zed.get_distance_at_point(int(position[0]), int(position[1]))

        return image

    def hough_lines(self, image):
        crunch =  160 # crunch rate (number of subdivs, lower=more crunch) 720 = no crunch
        min = 250
        max = 75
        downsampled_image = gate_detection.downsample_image(image,crunch,min,max)
        edges = cv2.Canny(downsampled_image,50,150,apertureSize = 3)
        lines = cv2.HoughLinesP(image=edges,rho=1,theta=np.pi/180, threshold=100,lines=np.array([]), minLineLength=100,maxLineGap=80)
        a,b,c = lines.shape
        print(a)
        for i in range(a):
            print(b)
            if b == 0:
                cv2.line(image, (lines[i][0][0], lines[i][0][1]), (lines[i][0][2], lines[i][0][3]), (0, 0, 255), 3, cv2.LINE_AA)
        return image

    def run_gate_detection(self, image):
        crunch =  160 # crunch rate (number of subdivs, lower=more crunch) 720 = no crunch
        minimim = 250   
        maximum = 50
        downsampled_image = gate_detection.downsample_image(image,crunch,minimim,maximum)
        middle_row_list, pitch_offset = gate_detection.correct_equator(downsampled_image, self.orientation_x.value)
        small_gaps_filled = gate_detection.fill_small_gaps(middle_row_list, int(len(middle_row_list) * .01)) # min gap relative to image width in pixels
        no_horizontal = gate_detection.get_rid_of_max_consecutives(small_gaps_filled, 20)

        average_unweighted_positions = gate_detection.average_cluster_positions(no_horizontal)
        weighted_position = gate_detection.weighted_cluster_position_average(average_unweighted_positions, .7, downsampled_image.shape[1]) # weight is 0-1, higher = more weighted towards center
        new_offset_is_valid = self.check_valid.storing_frames(weighted_position)
        if new_offset_is_valid: self.validated = True
        if self.validated:
            if abs(weighted_position - downsampled_image.shape[1] / 2) < self.hard_deadzone:
                self.locked = True
            if self.locked:
                print("Locked!!")
                self.self.shared_memory_object.gate_offset[0].value = 1
            #     if weighted_position == 0: 
            #         weighted_position = 1 # move forward if doesnt see anything after locking
            #     self.self.shared_memory_object.gate_offset[0].value = max(-self.hard_deadzone, min(weighted_position, self.hard_deadzone)) # Clamping to hard deadzone to move forward
            else: self.self.shared_memory_object.gate_offset[0].value = weighted_position - downsampled_image.shape[1] / 2 if weighted_position != 0 else 0

        return_image = downsampled_image
        return_image = cv2.cvtColor(return_image, cv2.COLOR_GRAY2BGR)
        print("positions len", average_unweighted_positions)
        for position in average_unweighted_positions:
            return_image = gate_detection.show_clusters(return_image, position, False, pitch_offset)
        return gate_detection.show_offset(return_image, weighted_position, new_offset_is_valid, pitch_offset)

    def run_wall_detection(self, image):
        crunch =  600 # crunch rate (number of subdivs, lower=more crunch) 720 = no crunch
        min = 255
        max = 20
        downsampled_image = gate_detection.downsample_image(image,crunch,min,max)
        middle_row_list = gate_detection.find_equator(downsampled_image, 180)
        position = gate_detection.count_changes(middle_row_list)
        print("median: \t" + str(self.zed.get_median_distance(360, 240, 200, 150)))
        self.shared_memory_object.gate_offset[0].value = position
        return downsampled_image

    def run_loop(self):
        """
            main loop for vision code
            opens camera,
            runs detection,
            gets distance,
            gets imu data,
            sends image to server (if enabled)
        """
        print("LOOP")
        show_boxes = True
        show_distance = False
        imu_enable = True
        send_image = False

        iteration = 0

        self.check_valid = CheckValid()

        self.create_camera_object()
        #self.detection = yv5.ObjDetModel(self.model_path)

        #create socket object
        if send_image:
            socket = self.connect_to_server()
        
        # while self.running.value:
        while True:
            iteration += 1
            image = None
            if self.shared_memory_object.gate_enable.value:
                image = self.zed.get_distance_image()
            elif self.shared_memory_object.yolo_enable.value:
                image = self.get_image()

            if image is None:
                print("NO IMAGE")
                continue
            results = None
            #run color detection
            if self.shared_memory_object.gate_enable.value:
                pass
                #image = self.run_color_detection(image, self.color)
                image = self.run_gate_detection(image)
                #image = self.hough_lines(image)
                #image = self.run_wall_detection(image)
                # print("COLOR OFFSET", self.color_offset_x.value, "\t", self.color_offset_y.value)
                
            #run yolo detection
            if self.shared_memory_object.yolo_enable.value:
                image = self.run_color_detection(image, self.color)

            #starting imu code
            if (import_success and imu_enable and self.zed is not None):
                self.share_imu_to_shared_memory()

            #get distance image from the zed if zed is initialized and user added the show distance argument
            if self.zed is not None and show_distance:
                image = self.zed.get_distance_image()

            # try:
            #     # cv2.imshow("image_test", image)
            #     #cv2.imwrite(f'frame{iteration}', image) 
            #     # cv2.waitKey(1)
            # except:
            #     pass
            
            if send_image:
                send_process = multiprocessing.Process(target = self.send_image_to_socket, args=(socket, image))
                send_process.start()
