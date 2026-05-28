# Sensor Fusion
Program to obtain position data of the sub using multiple AHRS modules, including sparton or trax.

### Outline

- Date Created: 05/28/2026
- Contributors:
    - Erik Dupourque (GitHub: @EDupourque, Discord: @zzuggy)
    - Chris Zueck (Github: @chriszueck, Discord: @squiggur)
- Dependencies:
    - Pyserial 3.5


### Key Files

- algorithm.py
  - This script computes the position data using the data retrieved from the sensors. The script also includes a test version using simulated values.

- fusion_testbench.py
    - This script contains a list of different runtimes and simulated acceleration values to test the algorithm. The output is compared with the expected value to measure accuracy.

- sparton_fusion_datapy
    - This script continuously reads acceleration, gyroscope, and compass data from the Sparton GEDC-6E / GEDC-6 and stores the values in shared memory.
    - This script is ran as a process within algorithm.py

### Usage

- Run algorithm.py to compute/print position data
- Run testbench.py to print comparison between computed and expected position

### Notes

- The final algorithm will use 3 sensors.
- Sparton BAUDRATE is 115200

### Status

- Current status: Testing algorithm and model testbench to get accurate position from messy data.
