class Color_Config_Parser:
    """
        discord: @kialli
        github: @kchan5071
        
        This class is used to parse a config file that contains color filters for the color_filter.py file.

        The config file should be formatted as follows:
        color_name: r,g,b (no spaces between the commas)

        by default, the config file is named "color_filter_config"
    """

    def __init__(self):
        self.config_file = "color_filter_config"
        self.colors      = []

    def get_colors(self):
        """
            returns a list of color objects that contain the color and the name of the color
        """
        return self.colors

    def parse_config(self):
        """
            parses the config file and stores the colors in a list of color objects, use get_colors to get the list
        """
        self.colors = []
        with open(self.config_file, "r") as file:
            config_string = file.readline()
            while config_string != "" and config_string is not None:
                #getting the name of the color
                name = config_string.split(" ")[0].strip(":")

                #this cursed line is used to get the color values from the config file
                color_list_string = config_string.strip().split(" ")[1].split(",")

                color_list_integers = []
                for color_string in color_list_string:
                    color_list_integers.append(int(color_string))

                self.colors.append(self.Color(color_list_integers, name))
                config_string = file.readline()

    def add_color(self, color, name):
        """
            adds a color to the config file

            input:
                color: a list of 3 integers that represent the rgb values of the color
                name: the name of the color
        """
        with open(self.config_file, "a") as file:
            file.write(name + ": ")
            for i in range(len(color)):
                file.write(str(color[i]))
                if i != len(color) - 1:
                    file.write(",")
                    self.colors.append(self.Color(color, name))
            file.write("\n")

    def find_color(self, name):
        """
            finds the index of the color in the config file
            
            input:
                name: the name of the color
            returns:
                the index of the color in the config file, -1 if the color is not found
        """
        with open(self.config_file, "r") as file:
            index = 0
            config_string = file.readline()
            while config_string != "":
                if config_string.startswith(name):
                    return index
                config_string = file.readline()
                index += 1

        return -1

    def remove_color(self, name):
        """
            removes a color from the config file

            USES find_color

            input:
                name: the name of the color
            returns:
                True if the color was removed, False if the color was not found
        """
        if self.find_color(name) == -1:
            return
        with open(self.config_file, "r") as file:
            lines = file.readlines()
        with open(self.config_file, "w") as file:
            for line in lines:
                if not line.startswith(name):
                    file.write(line)
                else:
                    self.colors.pop(self.find_color(name))
                    return True
        return False

    class Color:
        """
            Color class that contains the color and the name of the color

            properties:
                name: the name of the color
                color: the rgb values of the color, stored as a list of 3 integers
        """
        def __init__(self, color, name):
            self.name = name
            self.color = color

        def get_colors(self):
            return self.color
        
        def get_name(self):
            return self.name
        
        def __lt__(self, other):
            return self.name < other.name
        
        def __eq__(self, other):
            return self.name == other.name
        
        def __gt__(self, other):
            return self.name > other.name


#small tester - TO DO: make a better tester lmao
if __name__ == "__main__":
    parser = Color_Config_Parser()
    parser.parse_config()
    saved_colors = parser.get_colors()
    
    for color in saved_colors:
        parser.remove_color(color.get_name())

    parser.add_color([0, 0, 255], "blue")
    parser.add_color([0, 255, 0], "green")
    parser.add_color([255, 0, 0], "red")

    parser.parse_config()
    colors = parser.get_colors()

    print("Colors after adding red, green, and blue")
    for color in colors:
        print(color.get_name(), color.get_colors())

    print("Removing Red", parser.remove_color("red"))
    parser.parse_config()

    colors = parser.get_colors()

    print("Colors after removing red")
    for color in colors:
        print(color.get_name(), color.get_colors())
        
    parser.remove_color("green")
    parser.remove_color("blue")

    parser.parse_config()
    colors = parser.get_colors()

    print(len(colors))
    if len(colors) != 0:
        print("Failed")
    else:
        print("Passed")

    for color in saved_colors:
        parser.add_color(color.get_colors(), color.get_name())

