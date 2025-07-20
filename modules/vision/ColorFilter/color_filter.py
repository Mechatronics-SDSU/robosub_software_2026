import numpy as np
import cv2

class ColorFilter:
    """
        discord: @kialli
        github: @kchan5071
        
        This class filters out a specific color from an image and returns the image with only the color in it.
        It also returns the average position of the color in the image.
    """
    
    def __init__(self):
        self.sensitivity        = 10
        self.color_target       = [255, 0, 0]
        self.amount_in_image    = 1
        self.alpha_threshold    = 10
        self.iterations         = 10

    def set_color_target(self, color):
        """
            sets the color that the filter will target
        """
        self.color_target = color

    def get_image(self, image):
        """
            from an image, returns an image with only the target color in it

            IMPORTANT: will automatically adjust the sensitivity of the filter based on the amount of the target color in the image

            input:
                image: the image to filter

            output:
                the image with only the target color in it
                returns None if the image is None
        """
        if image is None:
            return None
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        lower_color = np.array([self.color_target[0] + self.sensitivity, 
                                self.color_target[1] + self.sensitivity, 
                                self.color_target[2] + self.sensitivity])
        upper_color = np.array([self.color_target[0] - self.sensitivity,
                                self.color_target[1] - self.sensitivity,
                                self.color_target[2] - self.sensitivity])
        mask = cv2.inRange(image, lower_color, upper_color)
        result = cv2.bitwise_and(image, image, mask=mask)

        #find average of the image
        pixels = image.shape[0] * image.shape[1]

        if np.sum(mask) / pixels < self.amount_in_image:
            self.sensitivity -= 1

        elif np.sum(mask) / pixels > self.amount_in_image:
            self.sensitivity += 1

        result = self.dilate_image(result)
        result = self.erode_image(result)

        return self.remove_values_below_threshold(result)
    
    def dilate_image(self, image):
        """
        dilates the image

        image dialation is a process that expands the boundaries of the image

        input:
            image: the image to dilate

        output:
            the dilated image
            returns None if the image is None
    """
        if image is None:
            return None
        element = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
        return cv2.dilate(image, element, self.iterations)
    
    def erode_image(self, image):
        """
            erodes the image

            image erosion is a process that shrinks the boundaries of the image

            input:
                image: the image to erode

            output:
                the eroded image
                returns None if the image is None
        """
        if image is None:
            return None
        element = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
        return cv2.erode(image, element, self.iterations)
    
    def downsample_image(self, image, block_size):
        """
            downsamples the image(shrinks the image)

            input:
                image: the image to downsample
                block_size: the size of the block to downsample by

            output:
                the downsampled image
                returns None if the image is None
        """
        if image is None:
            return None
        #divides image into blocks
        cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        width, height, _ = image.shape
        x_scaling = width / block_size
        y_scaling = height / block_size
        down_sized = cv2.resize(image, (0, 0), fx=1/x_scaling, fy=1/y_scaling)
        upsized = cv2.resize(down_sized, (0, 0), fx=x_scaling, fy=y_scaling)
        return upsized
    
    def remove_values_below_threshold(self, image):
        """
            removes values below a certain threshold (alpha_threshold) from the image
            and sets them to black

            input:
                image: the image to remove values from

            output:
                the image with values below the threshold removed
                returns None if the image is None
        """
        if image is None:
            return None
        image[image < self.alpha_threshold] = 0
        return image
    
    def remove_values_below_threshold(self, image, alpha_threshold):
        """
            removes values below a certain threshold (alpha_threshold) from the image
            and sets them to black

            input:
                image: the image to remove values from

            output:
                the image with values below the threshold removed
                returns None if the image is None
        """
        if image is None:
            return None
        image[image < alpha_threshold] = 0
        return image

    def get_average_position(self, image):
        """
            gets the average position of the target color in the image

            input:
                image: the image to get the average position from

            output:
                the average position of the target color in the image
                returns None if the image is None
        """
        if image is None:
            return None
        
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 100, 255, cv2.ADAPTIVE_THRESH_MEAN_C)
        valid_pixels = np.where(thresh > 0)

        if len(valid_pixels) == 0:
            return None
        
        x = np.mean(valid_pixels[1])
        y = np.mean(valid_pixels[0])

        if np.isnan(x) or np.isnan(y):
            return None
        return (x, y)

    def auto_average_position(self, image):
        """
            automatically gets the average position of the target color in the image

            calls get_image and get_average_position

            input:
                image: the image to get the average position from

            output:
                the average position of the target color in the image as a tuple
                returns None if the image is None
        """
        image = self.get_image(image)
        return self.get_average_position(image)

if __name__ == '__main__':
    cap = cv2.VideoCapture(0)
    filter = ColorFilter()
    while True:
        image = cap.read()
        box = filter.auto_average_position(image)

        if box is not None:
            image = cv2.circle(img=image, center=(int(box[0]), int(box[1])), radius= 10, color=(255, 0, 0), thickness=2)
        print(box)
        cv2.imshow('image', image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
