#!/bin/bash

# Creates the yaml file with dynamic class support
# Usage: ./yaml_maker.sh class1 class2 class3...

# Get all arguments as classes
CLASSES=("$@")

# Verify at least one class provided
if [ ${#CLASSES[@]} -eq 0 ]; then
    echo "Error: Please specify at least one class" >&2
    echo "Usage: $0 class1 class2 class3..." >&2
    exit 1
fi

# Create data directory if needed
mkdir -p yolov5/data

# Generate class dictionary for YAML
class_dict=""
for i in "${!CLASSES[@]}"; do
    class_dict+="  $i: ${CLASSES[$i]}"$'\n'
done

# Create data.yaml with proper formatting
cat <<EOL > yolov5/data/data.yaml
# data.yaml

# Paths
train: ../../Output_Data_Here/images/train
val: ../../Output_Data_Here/images/valid
test: ../../Output_Data_Here/images/test

# Class Names
names:
$class_dict
# Number of Classes
nc: ${#CLASSES[@]}
EOL

# Safely update model YAML (preserve other settings)
if [ -f "yolov5/models/yolov5m.yaml" ]; then
    # Create backup
    cp yolov5/models/yolov5m.yaml yolov5/models/yolov5m.yaml.bak
    
    # Update only the nc parameter
    awk -v nc="${#CLASSES[@]}" '/^nc:/ {$0="nc: "nc} 1' yolov5/models/yolov5m.yaml.bak > yolov5/models/yolov5m.yaml
    
    echo "Updated yolov5m.yaml with nc=${#CLASSES[@]}"
else
    echo "Error: yolov5/models/yolov5m.yaml not found" >&2
    exit 1
fi

echo "Configuration complete with classes: ${CLASSES[*]}"
