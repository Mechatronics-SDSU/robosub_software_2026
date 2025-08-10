from trax_fxns import TRAX
import time

def raw_data_test():
    trax = TRAX(baud=9600)
    
    if not trax.connect():
        print("Failed to connect to TRAX")
        return
    
    try:
        print("\n=== Starting Raw Data Test ===")
        
        # Send a basic command
        print("Sending kGetModInfo command...")
        trax.send_packet("kGetModInfo")
        
        # Set up raw monitoring
        print("\nListening for raw data (timeout: 5 seconds)...")
        start_time = time.time()
        while time.time() - start_time < 5:
            # Read raw bytes without parsing
            raw_bytes = trax.ser.read_all()
            if raw_bytes:
                print(f"Raw bytes received: {raw_bytes.hex(' ')}")
            else:
                print(".", end="", flush=True)
            time.sleep(0.1)
            
        print("\n\n=== Test Complete ===")
        
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        trax.close()

if __name__ == "__main__":
    raw_data_test()
