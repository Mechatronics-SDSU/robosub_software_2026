import vision.Yolov5Detection                           as yv5
import vision.Socket_Client                             as Socket_Client
import vision.gui_helper                                as gui_helper

from vision.ColorFilter.color_filter                    import ColorFilter
from vision.ColorFilter.color_filter_config_parser      import ColorFilterConfigParser

import math
import cv2
import multiprocessing
import time
from multiprocessing                                    import Value



#-----------------------------testing for zed sdk-------------------------
import_success = True
try:
    import pyzed.sl                                     as sl 
    from vision.Zed_Wrapper                             import Zed
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

    def __init__(self,  linear_acceleration_x ,  linear_acceleration_y,  linear_acceleration_z, 
                        angular_velocity_x,      angular_velocity_y,     angular_velocity_z, 
                        orientation_x,           orientation_y,          orientation_z, 
                        distance,
                        yolo_offset_x,           yolo_offset_y,
                        color_offset_x,          color_offset_y,
                        color,
                        color_enable,            yolo_enable):
        self.zed = Zed()
        self.cap = None
        self.linear_acceleration_x = linear_acceleration_x
        self.linear_acceleration_y = linear_acceleration_y
        self.linear_acceleration_z = linear_acceleration_z
        self.angular_velocity_x = angular_velocity_x
        self.angular_velocity_y = angular_velocity_y
        self.angular_velocity_z = angular_velocity_z
        self.orientation_x = orientation_x
        self.orientation_y = orientation_y
        self.orientation_z = orientation_z
        self.distance = distance
        self.yolo_offset_x = yolo_offset_x
        self.yolo_offset_y = yolo_offset_y

        self.color_offset_x = color_offset_x
        self.color_offset_y - color_offset_y
        self.color = color
        self.yolo_enable = yolo_enable


        self.color_filter_enable = color_enable
        self.color_filter = ColorFilter()

        self.model_path = './models_folder/yolov5m.pt'
        self.detection = yv5.ObjDetModel(self.model_path)
        
        
        self.detection = None
        self.skip_frames = 0
        self.frame_count = self.skip_frames

        self.zed, self.cap = self.create_camera_object()
    
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
        self.color_filter_enable = True

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
        zed = None
        cap = None
        #import success tests if zed sdk imported successfully
        if import_success:
            zed = Zed()
            state = zed.open()
            if state != sl.ERROR_CODE.SUCCESS:
                zed = None
                print("Zed camera not found, using webcam")
                cap = cv2.VideoCapture(0)
        else:
            zed = None
            print("camera library not found, using webcam")
            cap = cv2.VideoCapture(0)

        return zed, cap

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

    def get_image(self, zed, cap):
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
        if zed is not None:
            image = zed.get_image()
        elif cap is not None:
            _, image = cap.read()
        else:
            print("No camera found, exiting")
        
        return image

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
        self.linear_acceleration_x.value = lin_acc[0]
        self.linear_acceleration_y.value = lin_acc[1]
        self.linear_acceleration_z.value = lin_acc[2]
        self.angular_velocity_x.value = ang_vel[0]
        self.angular_velocity_y.value = ang_vel[1]
        self.angular_velocity_z.value = ang_vel[2]
        self.orientation_x.value = orientation[0]
        self.orientation_y.value = orientation[1]
        self.orientation_z.value = orientation[2]

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
            self.yolo_offset_x.value, self.yolo_offset_y.value = self.get_yolo_offset(box, results, image)
            self.distance.value = float(distance)
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

        position = self.color_filter.auto_average_position()
        self.color_offset_x.value = position[0] - image.shape[1] // 2
        self.color_offset_y.value = position[1] - image.shape[0] // 2
        if self.zed is not None:
            self.distance.value = self.zed.get_distance_at_point(position[0], position[1])

        return image
    
    def down_sample_detection(self, image):
        """
            down samples image and gets average position of color/distance

            input
                image: np_array

            return
                image: np_array
                results: tuple
        """
        image = self.color_filter.remove_values_below_threshold(image, 40)
        image = self.color_filter.downsample_image(image)
        results = self.color_filter.get_average_position(image)
        return image, results
    

    def run_loop(self):
        """
            main loop for vision code
            opens camera,
            runs detection,
            gets distance,
            gets imu data,
            sends image to server (if enabled)
        """
        show_boxes = True
        show_distance = False
        imu_enable = False
        send_image = False

        #create socket object
        if send_image:
            socket = self.connect_to_server()
        
        while True:
            image = self.get_image(self.zed, self.cap)
            results = None
            #run color detection
            if self.color_filter_enable:
                image = self.run_color_detection(image, self.color)
            #run yolo detection
            if self.yolo_enable:
                image = self.run_yolo_detection(show_boxes, image)

            #starting imu code
            if (import_success and imu_enable and self.zed is not None):
                self.share_imu_to_shared_memory()

            #get distance image from the zed if zed is initialized and user added the show distance argument
            if self.zed is not None and show_distance:
                image = self.zed.get_distance_image()
            
            if send_image:
                send_process = multiprocessing.Process(target = self.send_image_to_socket, args=(socket, image))
                send_process.start()


if __name__ == '__main__':
    loop_object = VideoRunner(None)
    loop_object.run_loop()
