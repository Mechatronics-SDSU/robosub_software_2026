#!/bin/bash

# Script Name: robo_robo.sh
# Author: Ryan Sundermeyer
# Date: 8/7/2024
# Description: Reset/kill robot

# send can kill
echo "sending can kill"
cansend can0 000\#
# kill all python and zed processes
echo "killing python processes (failures ok)"
pkill -f python3
echo "killing zed processes (failures ok)"
pkill -f zed
# send can all-clear
echo "sending can all-clear"
cansend can0 00A\#
echo "Done."