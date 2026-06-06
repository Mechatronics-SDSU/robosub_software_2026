# PID Control
PID control for motors given DVL values (or other if configured correctly)

### Outline

- Date Created: 6/23/2024
- Contributors:
    - Ryan Sundermeyer (GitHub: @rsunderr, Discord: @.kech)
    - Kai Chan (GitHub: @kchan5071, Discord: @kialli)
    - Sam Georges (GitHub: @thesamgeorges, Discord: @smoonth.)
    - Joe Lofrese (GitHub: @Joelofrese, Discord: @croppie_luvr)

- Dependencies:
    - numpy 1.24.3

### Key Directories

- N/A

### Key Files

- pid_interface.py
    - Interface file connecting PID control to the main backbone using shared memory
- six_dof_pid.py
    - How all of the different files communicate, through a list of shared variables passed through an object


### Usage

- during runtime call: run_pid()
    - takes in 6 axis target and 6 axis DVL readings to produce global and local space motor commands to move towards
      the target

### Notes

- If this process is active and the target location/rotation does not match eachother, running run_pid() will generate 
  the motor values
- six_dof_pid.py can be VERY easily pulled out by itself, so if the codebase gets rewritten it should be easy to port

### Status

- Current status: Complete

### Improvements

- K values array should be parameterized instead of hardcoded
- find a better way to switch between depth sensor and DVL to minimize depth drift
- setup proper logging instead of debug prints
- add typing
