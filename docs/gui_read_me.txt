# Graphical User Interface
A simple locally hosted web interface to help run commands and edit values for the sub

### Outline

- Date Created: 05/25/26
- Contributors:
    - Malaika Joiner (GitHub: @malaikajoiner, Discord: @314_piekitty)
    - Ana Morais (GitHub: @AnaMoraisA, Discord: @anamorais_21358)
- Dependencies:
    - asgiref 3.11.0 
    - Django 6.0.1
    - PyYAML 6.0.3
    - ruamel.yaml 0.19.1
    - sqlparse 0.5.5

### Key Directories

- modules/gui
    - All of the main gui components is inside the gui folder.
    - Sub-folder "mysite" contains django settings and subfolder "web_gui" has most of the other relavent files.
- modules/objects_yaml_COPIES
    - A folder that contains previously saved values of the objects.yaml file.
- modules/gui/web_gui/templates
    - All HTML templates for the gui must be contained in this folder.

### Key Files

- start.py
    - Python file that initializes the gui object and allows the webserver to run.
- objects.yaml
    - The gui will read values and edit values in this yaml file.
    - Yaml file contains information for PID, mode lists, and course values.
- modules/objects_yaml_COPIES/default.yaml
    - Backup of the default objects.yaml file. 
    - In order to chage the default, the file name must be titled "default.yaml", and only one can exist.
- modules/gui/web_gui/gui_launch.py
    - class for the gui object. This object will constantly write shared memory values to a JSON file.
- modules/gui/web_gui/objects_yaml_writer.py
    - class for an object used for changing the values in objects.yaml
- modules/gui/web_gui/views.py
    - Python functions intended to be called by the gui should be defined in here for easy access from HTML/javascript files.
- modules/gui/web_gui/urls.py
    - All functions in views.py must have a line in urls.py in order to be accessible.
    - Use the template: "path('title/', views.title, name = 'title'),"

### Usage

- Run "python3 start.py" to activate a server at http://127.0.0.1:8000/
- To turn off server, control-c
- "Start" button on homepage runs the sub with start_button.py
- "Launch" button on homepage runs launch.py
- "Soft Kill" button on homepage runs soft_kill.py
- "Hard Kill" button on homepage runs hard_kill.sh
- "View Telemetry" button on homepage redirects you to a page that displays DVL values
- "PID Tuning" button on homepage redirects you to a page that lets you read and change the PID values in objects.yaml
- "Mission Planner" button redirects you to a page with two buttons
    - "Edit Mode List" button redirects you to a page that lets you change the mode list for courses
    - "Edit Courses" button redirects you to a page that lets you edit the other main yaml values
- Toggle at top left corner can switch the theme from Light and Dark mode

### Notes

- How to add new page/functions
    - to create a new page:
        - create an HTML file in modules/gui/web_gui/templates
        - add a function definition in modules/gui/web_gui/views.py using this template:
            - def name(request): 
                return render(request, "name.html", {"color_mode": color_mode})
            - note: (optional) color_mode is used to make page compatible with Light/Dark modes. Check other HTML files for examples on how the color mode is used.
        - add a line in modules/gui/web_gui/urls.py using this template:
            - "path('title/', views.title, name = 'title'),"
            - the "title" should match the name of the render function defined in views.py.
        - you can use javascript in the html templates to call python functions in views.py using commands such as fetch("{% url 'title' %}");
    - to create a new function:
        - define new python functions in modules/gui/web_gui/views.py
        - call the functions from html templates using javascript (explained above)
- How to add a new course:
    - Note: must manually initialize new course values in objects.yaml first before making it accessible by the gui
    - Follow commented directions inside modules/gui/web_gui/templates/edit_courses.html
        - (there are 3 steps in edit_courses.html, term search "ADD NEW COURSE" to find)
    - Follow comented directions inside modules/gui/web_gui/templates/edit_mode_list.html
        - (there is 1 step in edit_mode_list.html, term search "ADD NEW COURSE" to find)
- How to add new Mode:
        - Follow comented directions inside modules/gui/web_gui/templates/edit_mode_list.html
        - (there is 1 step in edit_mode_list.html, term search "ADD NEW MODE" to find)

### Status

- Current status:  Ready for Approval 

### what needs to be tested:

- test if both launch.py and start.py is able to initialize a shared memory object regardless of which command is ran first
- test if DVL reset button works (on view telemetry page)
- test if all start and kill buttons work