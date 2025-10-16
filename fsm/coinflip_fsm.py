from utils.socket_send                            import set_screen
from fsm.fsm                                    import FSM_Template
from modules.sensors.trax2.trax_fxns         import TRAX
import yaml, os, subprocess
"""
    discord: @.kech
    github: @rsunderr

    FSM for coin flip
    
"""

class CoinFlip_FSM(FSM_Template):
    """
    FSM for coin flip mode - aiming toward gate after being turned by diver
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Coin Flip FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "COIN_FLIP"

        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 0.3#m
        self.z_buffer = 1#m
        self.yaw_buffer = 15#deg

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.pool_yaw, self.depth = (None, None)
        self.trax_yaw = 90 # default has a chance of being correct
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.depth = data['objects']['coin_flip']['yaw']
            self.pool_yaw = data['objects']['coin_flip']['yaw']
            if self.pool_yaw > 180: self.pool_yaw = self.pool_yaw - 360 # correct for dvl range [-180,180]

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        print("STARTING COIN_FLIP MODE")

        # GET TRAX DATA --------------------------------------------------------------------------------------------------------------------------------
        try:
            subprocess.run(["sudo", "chmod", "777", "/dev/ttyUSB1"], check=True)
            print("updated USB1 perms")
        except:
            pass

        trax = TRAX()
        trax.connect()

        # kSetDataComponents
        frameID = "kSetDataComponents"
        payload = (1, 0x5)
        trax.send_packet(frameID, payload)

        # kGetData
        frameID = "kGetData"
        trax.send_packet(frameID)

        # kGetDataResp
        # TODO make it try catch to read first resp, then take a few angles and average them
        try:
            data = trax.recv_packet(payload)
            if len(data) == 6:
                print(f"\n{data[4]} degrees")
                self.trax_yaw = data[4]
        except: # FIXME try again
            try:
                data = trax.recv_packet(payload)
                if len(data) == 6:
                    print(f"\n{data[4]} degrees")
                    self.trax_yaw = data[4]
            except:
                print("TRAX FAILED")

        if self.trax_yaw > 180: self.trax_yaw = self.trax_yaw - 360 # correct for dvl range [-180,180]

        trax.close()


        # set initial state
        self.next_state("SPIN")

    def next_state(self, next: str) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case "INIT": return # initial state
            case "SPIN": # drop to correct depth and turn towards gate
                self.shared_memory_object.target_yaw.value = self.pool_yaw
                #self.shared_memory_object.target_z.value = self.depth
            case "DONE": # disable but not kill (go to next mode)
                # TODO re-zero the dvl values
                self.active = False
                self.complete = True
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID NEXT STATE {next}")
                return
        self.state = next
        print(f"{self.name}:{self.state}")

    def loop(self) -> None:
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        self.display(150, 0, 150) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT" | "DONE": return
            case "SPIN": # transition: SPIN -> DONE
                if abs(self.shared_memory_object.dvl_yaw.value - self.trax_yaw) <= self.yaw_buffer and abs(self.shared_memory_object.dvl_z.value - self.depth) <= self.z_buffer:
                    self.next_state("DONE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

