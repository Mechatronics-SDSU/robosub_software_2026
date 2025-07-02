import torch
import cv2
from ultralytics import YOLO
import torch


'''
    discord: @kialli
    github: @kchan5071
    
    class to run object detection model
    
    self explanatory usage
    
'''


class ObjDetModel:

    def __init__(self, model_name):
        print("initializing yolo object")
        # load pretrained model
        torch.cuda.set_device(0)
        self.model_resolution = 640
        self.model = torch.hub.load('ultralytics/yolov5', 'custom', path =  model_name, device = 0)
        print("yolo init success")

    def load_new_model(self, model_name):
        self.model = torch.hub.load('ultralytics/yolov5', 'custom', path = './models_folder/' + model_name, device = 0)

    def detect_in_image(self, image):
        #convert color space 
        frame_cc = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        #resize image to 640 x 640
        frame_squeeze = cv2.resize(frame_cc, (self.model_resolution, self.model_resolution))

        # Run the YOLO model
        results = self.model(frame_squeeze)

        #resize results according to resolution
        x_resolution = int(image.shape[1])
        y_resoltion = int(image.shape[0])

        x_ratio = x_resolution / self.model_resolution
        y_ratio = y_resoltion / self.model_resolution

        #fix resolution
        with torch.inference_mode():
            for box in results.xyxy[0]:
                if box[5] == 0:
                    box[2] = int(x_ratio * box[2])
                    box[0] = int(x_ratio * box[0])
                    box[3] = int(y_ratio * box[3])
                    box[1] = int(y_ratio * box[1])


        return results
            
        
