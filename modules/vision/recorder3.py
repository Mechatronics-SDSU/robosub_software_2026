import pyzed.sl as sl
import cv2
import copy
import statistics
import os
import time
import sys
import numpy as np
from Zed_Wrapper   import Zed

"meows"

class Recorder:
    def __init__(self):
        self.zed = sl.Camera()
        self.init_params                            = sl.InitParameters()
        self.init_params.camera_resolution          = sl.RESOLUTION.HD720
        self.init_params.camera_fps                 = 24
        self.init_params.svo_real_time_mode         = False
        self.runtime_parameters                     = sl.RuntimeParameters()

    def startRec1(self, videoFolderPath, videoName, amountTime):

        status = self.zed.open(self.init_params)

        if status != sl.ERROR_CODE.SUCCESS: 
            print("Camera not Opened")
            exit(1)
        
        frames=0  
        image = sl.Mat()
        self.zed.retrieve_image(image, sl.VIEW.LEFT)
        temp= image.get_data()
        height, width, channels= temp.shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        newVideoPath = os.path.join(videoFolderPath,f"{videoName}.mp4" )
        video = cv2.VideoWriter(newVideoPath, fourcc, 24, (width, height))
        start_time = time.time()
        end_time = start_time + amountTime
        
        while time.time() < end_time:

            if self.zed.grab(self.runtime_parameters) == sl.ERROR_CODE.SUCCESS:
                self.zed.retrieve_image(image, sl.VIEW.LEFT)
                img = image.get_data()
                img_out = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                video.write(img_out)
            # Convert ZED image to correct format
            
            frames+=1
            elapsed_time = time.time() - start_time
            time_to_wait = (frames / 24) - elapsed_time 
            #waits if pics are taken faster than needed
                
            if time_to_wait > 0:
                time.sleep(time_to_wait) 

        print("printed at "+str(frames/amountTime)+ " frames per second")
        self.zed.close()
        cv2.destroyAllWindows()
        video.release()
   
if __name__ == '__main__':

    videoName = sys.argv[1]
    amountTime = int(sys.argv[2])
    rec = Recorder()   
    videoFolderPath = "launch/vision/videos" #local path
    
    if not os.path.exists(videoFolderPath):
        os.makedirs(videoFolderPath)
        
    rec.startRec1(videoFolderPath, videoName, amountTime)

    
