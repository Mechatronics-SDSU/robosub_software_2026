#!/bin/bash


# Script Name: generate_docs
# Author: Kai Chan
# Date: 07/23/2024
# Description: Generates documentation for the project using pydoc

rm -rf docs
CUURENT_DIR=./
mkdir docs

files=$(find . -name "*.py")
for file in $files
do
    pdoc3 $file --html --output-dir docs
done


