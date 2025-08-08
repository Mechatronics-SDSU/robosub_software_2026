#!/bin/bash

# Script Name: yoloscript
# Author: Juan Cota
# Updated from a script written by: Ryan Sundermeyer, Joe Loffrees
# Date: 8/7/2025
# Description: Automates the terminal portion of training an AI model in yolov5

# Creates File Structure (If Not There)
mkdir Insert_Data_Here
mkdir scripts

EPOCHS=("$1")
WEIGHT=("$2")
shift 2
CLASSES=("$@")

echo "Cloning yolov5"
git clone https://github.com/ultralytics/yolov5 # clone repository
cd yolov5
echo "Installing Dependencies..."
pip install -r requirements.txt # install dependencies
cd ..
pwd
echo "Resizing Images..."
python3 "./scripts/image_resizer.py" # Resizes images into 640x640 resolution
echo "Running organizer..."
bash "./scripts/organizer.sh" # Sorts images/labels into test/train/valid folders
echo "Creating yaml file..."
bash "./scripts/yaml_maker.sh" "${CLASSES[@]}" # Automatically makes the yaml file

# Run yolov5 AI Model
echo "Running yolo..."
python3 yolov5/train.py --imgsz "640" --weights "$WEIGHT" --cfg "yolov5/models/yolov5m.yaml" --epochs "$EPOCHS" --data "yolov5/data/data.yaml"
