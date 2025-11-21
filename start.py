import django, sys, os, subprocess
from shared_memory                          import SharedMemoryWrapper

#File that starts up the website


shared_memory = SharedMemoryWrapper()

def main():
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

        # initialize object with shared memory
        gui_object = Gui_launch(shared_memory)

if __name__ == '__main__':
    main()
    print("RUN FROM LAUNCH")
