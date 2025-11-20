import django, sys, os, subprocess
from shared_memory                          import SharedMemoryWrapper

# create shared memory object
shared_memory = SharedMemoryWrapper()

def main():
        print("*\n*\n*\n   NOTE!!!! \n   if testing without the sub, make sure to comment out import launch in views.py\n   if connected to sub, uncomment import launch instead\n*\n*\n*")
        #sets up web gui
        BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
        GUI_DIR = os.path.join(BASE_DIR, "modules", "gui") 
        if GUI_DIR not in sys.path: sys.path.insert(0, GUI_DIR)
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
        django.setup()

        from modules.gui.web_gui.gui_launch         import Gui_launch

        subprocess.Popen(
            [sys.executable, "manage.py", "runserver"], 
            cwd=str(GUI_DIR), 
        )

        # initialize object
        gui_object = Gui_launch(shared_memory)

if __name__ == '__main__':
    main()
    print("RUN FROM LAUNCH")
