#!/bin/bash

# Create directories if they don't exist
mkdir -p Output_Data_Here/{images,labels}/{train,test,valid}
cd Output_Data_Here

# Organizes files into 70% train, 20% test, 10% valid

# Images
count=1
for file in "../Insert_Data_Here/resized_images"/*; do
    case $((count % 10)) in
        0|1|2|4|5|6|8) dest="train" ;;
        3|7)           dest="test" ;;
        9)             dest="valid" ;;
    esac

    # Moves into assigned destination 
    if [ -f "$file" ]; then
        mv "$file" "images/$dest/"
    fi

    ((count++))
done

# Labels
count=1
for file in "../Insert_Data_Here/labels"/*; do
    case $((count % 10)) in
        0|1|2|4|5|6|8) dest="train" ;;
        3|7)           dest="test" ;;
        9)             dest="valid" ;;
    esac

    # Moves into assigned destination 
    if [ -f "$file" ]; then
        cp "$file" "labels/$dest/"
    fi

    ((count++))
done
