import time
import logging
from multiprocessing import Process, Event
from trax_fxns import TRAX

class TraxProcess(Process):
    def __init__(self, shared_memory):
        super().__init__()
        self.shared_memory = shared_memory
        self.trax = TRAX()
        self._stop_event = Event()  # For clean shutdown
        self.logger = logging.getLogger('trax')
        
    def run(self):
        if not self._connect_and_setup():
            return
            
        try:
            while not self._stop_event.is_set():
                self._update_data()
        except Exception as e:
            self.logger.error(f"TRAX process error: {e}")
        finally:
            self._cleanup()

    def _connect_and_setup(self):
        if not self.trax.connect():
            self.logger.error("Failed to connect to TRAX AHRS")
            return False
        
        try:
            self.trax.send_packet("kSetDataComponents", (6, 5, 24, 25, 21, 22, 23))
            self.trax.send_packet("kStartContinuousMode")
            return True
        except Exception as e:
            self.logger.error(f"Setup failed: {e}")
            return False

    def _update_data(self):
        start_time = time.time()
        
        self.trax.send_packet("kGetData")
        data = self.trax.recv_packet(timeout=0.5)
        
        if data and len(data) >= 6:
            self.shared_memory.yaw = data[0]
            self.shared_memory.pitch = data[1]
            self.shared_memory.roll = data[2]
            self.shared_memory.accel_x = data[3]
            self.shared_memory.accel_y = data[4]
            self.shared_memory.accel_z = data[5]
        else:
            self.logger.warning("Invalid or no data received")

        elapsed = time.time() - start_time
        time.sleep(max(0.5 - elapsed, 0))

    def _cleanup(self):
        try:
            self.trax.send_packet("kStopContinuousMode")
        except:
            pass
        finally:
            self.trax.close()

    def stop(self):
        """Signal the process to stop"""
        self._stop_event.set()