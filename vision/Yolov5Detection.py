import yolov5
import cv2


class ObjDetModel:
    """
    discord: @kialli
    github: @kchan5071
    
    class to run object detection model
    
    self explanatory usage
    
    """

    def __init__(self, model_path):
        # load pretrained model
        self.model = yolov5.load(model_path)

    def load_new_model(self, model_path):
        """
            load a new model
            input
                model_path: path to new model
        """
        self.model = yolov5.load(model_path)

    def detect_in_image(self, image):
        """
            detect objects in an image
            input
                image: np_array
            return
                results: yolov5 results object
        """
        frame_cc = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Run the YOLO model
        results = self.model(frame_cc, 320)
        return results
        
