import cv2

"""
    discord: @kialli
    github: @kchan5071
    
    draw boxes and lines on image
    used in gui for testing
    not used in competition
"""

def draw_boxes(image, results):
    """
        draws bounding boxes on image
        input
            image: np_array
            results: yolov5 results object
        return
            image: np_array
    """
    for box in results.xyxy[0]:
        if box[5] == 0:
            xB = int(box[2])
            xA = int(box[0])
            yB = int(box[3])
            yA = int(box[1])
            cv2.rectangle(image, (xA, yA), (xB, yB), (0, 255, 0), 2)
    return image

def draw_lines(image, results):
    """
        draws lines from center of image to center of bounding boxes
        input
            image: np_array
            results: yolov5 results object
        return
            image: np_array
    """
    start = (0, 0)
    try:
        start = (int(image.shape[1] / 2), int(image.shape[0] / 2))
    except:
        return
    end = None
    for box in results.xyxy[0]:
            if box[5] == 0:
                xB = int(box[2])
                xA = int(box[0])
                yB = int(box[3])
                yA = int(box[1])
                end = ((xB + xA) // 2, (yB + yA) // 2)
                if end is not None:
                    cv2.line(image, start, end, (255, 255, 255), 5)
    return image