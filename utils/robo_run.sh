#!/bin/bash

# Script Name: robo_run.sh
# Author: Ryan Sundermeyer
# Date: 8/7/2024
# Description: Does all of the basic setup stuff for the robot

# kill all python and zed processes
pkill -f python3
pkill -f zed
# set up can
cd josephsDebugLand
echo "Calling setupCAN.sh"
echo "Password: tran2023"
./setupCAN.sh
echo "Calling do_not_run.sh"
./do_not_run.sh
cd ..
echo "Done."