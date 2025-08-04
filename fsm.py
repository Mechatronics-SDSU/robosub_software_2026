"""
    discord: @.kech
    github: @rsunderr

    FSM
    
"""
class FSM:
    def __init__(self):
        self.state = "S1"
        self.active = False

    def next_state(self, next):
        self.state = next
        match(next):
            case "S1":
                pass
            case _:
                print("INVALID STATE")
                return

    def loop(self):
        match(next):
            case "S1":
                pass
            case _:
                print("INVALID STATE")
                return
    
    def start(self):
        self.active = True
        # start processes
    
    def join(self):
        # join processes
        pass

    def stop(self):
        self.active = False
        # terminate processes