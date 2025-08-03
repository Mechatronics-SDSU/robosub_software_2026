# Color Filter for Vision

to add colors, add the name, then rgb values to the "color_filter_config" file in this format:

Color: R,G,B 

note: the rgb values should be integers, and there shouldnt be spaces in between the values

## Usage

### color_filter.py
does the cool stuff with opencv
theoretically all you need is the `auto_average_position()` method, however you can manually get an image, dialate/erode, clean it then call the `get_average_position()` method to find the average of the pixels left

### color_filter_config.py 
manages the config file to make everything easier

use `get_colors()` to get colors from the config file

you can find, add, and remove colors from the config file

you can manually update the colors in the list by calling `parse_config()`

#### colors
custom class to hold colors and the name, ONLY USED IN COLOR_FILTER_CONFIG

### color_filter_config
to add colors, add the name, then rgb values to the "color_filter_config" file in this format:

Color: R,G,B 

note: the rgb values should be integers, and there shouldnt be spaces in between the values
