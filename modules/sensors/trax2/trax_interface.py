from multiprocessing                        import Process, Value
#from shared_memory                          import SharedMemoryWrapper
from trax_fxns                              import TRAX
import time

class Trax_Interface(TRAX):

    """
    discord: @.kech
    github: @rsunderr
    """

    def __init__(self, shared_memory_object):
        """
        Trax interface constructor
        """
        self.shared_memory_object = shared_memory_object
        super().__init__()

    def run_loop(self):
        """
        Function targeted by looping multiprocessing calls, called only once
        """
        self.connect()

        # kSetAcqParams
        frameID = "kSetAcqParams"
        payload = (False, False, 0.0, 0.05) # T/F poll mode/cont mode, T/F compass FIR mode, PNI reserved, delay
        self.send_packet(frameID, payload)

        # kSetAcqParamsDone (optional)
        #data = self.trax.recv_packet()
        #print("kSetAcqParamsDone:", data[1] == 26)

        # kSetDataComponents
        frameID = "kSetDataComponents"
        payload = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
        self.send_packet(frameID, payload)

        # kStopContinuousMode
        frameID = "kStopContinuousMode"
        self.send_packet(frameID)

        # kStartContinuousMode
        frameID = "kStartContinuousMode"
        self.send_packet(frameID)

        while self.shared_memory_object.running.value:
            try:
                # get data
                data = self.recv_packet(payload)
            except KeyboardInterrupt:
                # kStopContinuousMode
                frameID = "kStopContinuousMode"
                self.send_packet(frameID)
                self.close()
    """
    def get_data(self, components):# 6 comp's: ax ay az yaw pitch roll
        payload = []
        if type(components[0]) == type("str"):
            for comp in components:
                match(comp):
                    case
    """
        
        # kSetDataComponents
        frameID = "kSetDataComponents"
        self.send_packet(frameID, payload)

        resp = []
        resp = self.recv_packet(payload)
        out = []
        i = 0
        #while i < len(resp):
            #if i >out.append(resp[i])
        return out

if __name__ == "__main__":
    shared_memory_object = "placeholder"
    trax = Trax_Interface(shared_memory_object)
    comps = ()
    trax.get_data()