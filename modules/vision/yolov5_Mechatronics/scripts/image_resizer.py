import cv2
import os

def resize_images_preserve_names(input_dir, output_dir, target_size=(640, 640)):
    """
    Resizes all images in input_dir and saves them to output_dir with original filenames
    Args:
        input_dir: Path to folder containing original images
        output_dir: Where to save resized images
        target_size: (width, height) tuple (default 640x640)
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Process all image files
    for filename in os.listdir(input_dir):
        # Check for image files
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            
            # Read, resize and save with original name
            img = cv2.imread(input_path)
            if img is not None:
                resized_img = cv2.resize(img, target_size)
                cv2.imwrite(output_path, resized_img)
            else:
                print(f"Warning: Could not read {filename}")

def main():
    # Configuration
    INPUT_DIR = "Insert_Data_Here/images"  # Original images
    OUTPUT_DIR = "Insert_Data_Here/resized_images"          # Where to save resized versions
    
    # Resize all images while keeping names
    resize_images_preserve_names(INPUT_DIR, OUTPUT_DIR)

if __name__ == "__main__":
    main()
