import cv2
import numpy as np

"""
This is a simple script to test the camera
dont overthink it
"""

def get_image(cap):
    ret, frame = cap.read()
    return frame

def initialize_camera():
    cap = cv2.VideoCapture(0)
    return cap

def main():
    cap = initialize_camera()
    while True:
        image = get_image(cap)
        if image is None:
            break
        cv2.imshow('image', image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()