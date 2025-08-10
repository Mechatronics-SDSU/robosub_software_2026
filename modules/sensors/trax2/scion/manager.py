from multiprocessing import Manager
import time
import signal
from trax_process import TraxProcess

def create_shared_memory():
    manager = Manager()
    shared = manager.Namespace()
    
    shared.yaw = None
    shared.pitch = None
    shared.roll = None
    shared.accel_x = None
    shared.accel_y = None
    shared.accel_z = None
    
    return manager, shared

def main():
    manager, shared_memory = create_shared_memory()
    trax_process = TraxProcess(shared_memory)
    
    def shutdown(signum=None, frame=None):
        print("\nShutting down...")
        trax_process.stop()
        #if trax_process.is_alive():
            #trax_process.join(timeout=2.0)
        manager.shutdown()
        exit(0)
        
    signal.signal(signal.SIGINT, shutdown)
    
    try:
        trax_process.start()
        
        while True:
            if None in (shared_memory.yaw, shared_memory.pitch):
                print("Waiting for initial data...")
            else:
                print(f"\rYaw: {shared_memory.yaw:.2f}° | "
                      f"Pitch: {shared_memory.pitch:.2f}° | "
                      f"Roll: {shared_memory.roll:.2f}°", end='', flush=True)
            
            time.sleep(0.1)
            
    except Exception as e:
        print(f"Error: {e}")
        shutdown()

if __name__ == "__main__":
    main()