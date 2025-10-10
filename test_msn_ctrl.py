from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from fsm.test_fsm                           import Test_FSM
from utils.socket_send                      import set_screen
from modules.test_module.test_process       import Test_Process
from fsm.gate_fsm                               import Gate_FSM
from fsm.slalom_fsm                             import Slalom_FSM
from fsm.octagon_fsm                            import Octagon_FSM
from fsm.return_fsm                             import Return_FSM
import time, os, random, yaml, subprocess


# import modules
# from modules.pid.pid_interface              import PIDInterface
# from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
# from modules.vision.vision_main             import VisionDetection
# from socket_send                            import set_screen
# from coinflip_fsm                           import CoinFlip_FSM


shared_memory_object = SharedMemoryWrapper()

gate_mode   = Gate_FSM(shared_memory_object, [])
slalom_mode = Slalom_FSM(shared_memory_object, [])
oct_mode    = Octagon_FSM(shared_memory_object, [])
return_mode = Return_FSM(shared_memory_object, [])
mode_list   = [gate_mode, slalom_mode, oct_mode, return_mode]


def move_toward(curr: float, target: float,
                k: float = 0.15,
                max_step: float | None = None,
                noise_scale: float = 0.05) -> float:
    # Move partway toward target, with random noise
    delta = (target - curr) * k
    disturbance = random.uniform(-noise_scale, noise_scale)
    delta += disturbance

    if max_step is not None:
        if delta >  max_step: delta =  max_step
        if delta < -max_step: delta = -max_step

    return curr + delta


def approx_equal(a: float, b: float, tol: float = 0.05) -> bool:
    return abs(a - b) <= tol
    

def get_targets_for_mode(mode_name: str, data: dict, profile: str = "test"):
    """
    Return exactly THREE values (tx, ty, tz) for the current mode.

    The YAML may contain extra fields (buffers, waypoints, pauses, etc.),
    but the motion loop only needs a single immediate (x, y, z) target.
    """
    root = data.get(profile, {})
    m = (mode_name or "").lower()

    if m == "gate":
        g = root.get("gate", {})
        # Prefer the final gate target (x, y, z); fall back to buffers if absent
        tx = float(g.get("x", g.get("x_buf", 0.0)))
        ty = float(g.get("y", g.get("y_buf", 0.0)))
        tz = float(g.get("z", g.get("z_buf", 0.0)))
        return tx, ty, tz

    elif m == "slalom":
        s = root.get("slalom", {})
        # Use first waypoint as the immediate target, and 'z' for depth
        tx = float(s.get("x1", s.get("x_buf", 0.0)))
        ty = float(s.get("y1", s.get("y_buf", 0.0)))
        tz = float(s.get("z",  s.get("z_buf", 0.0)))
        return tx, ty, tz

    elif m == "octagon":
        o = root.get("octagon", {})
        tx = float(o.get("x", o.get("x_buf", 0.0)))
        ty = float(o.get("y", o.get("y_buf", 0.0)))
        tz = float(o.get("z", o.get("z_buf", 0.0)))
        return tx, ty, tz

    elif m == "return":
        r = root.get("return", {})
        # Head toward first leg; use 'depth' if provided, else z_buf/0
        tx = float(r.get("x1", r.get("x_buf", 0.0)))
        ty = float(r.get("y1", r.get("y_buf", 0.0)))
        tz = float(r.get("depth", r.get("z_buf", 0.0)))
        return tx, ty, tz

    # Default: zeros
    return 0.0, 0.0, 0.0

# Link modes together in a linked list
def make_list(modes):
    for i in range(len(modes)-1):
        modes[i].next_mode = modes[i+1]
    modes[-1].next_mode = None


def display(mode):
    # Display current DVL and target positions
    sm = shared_memory_object
    print(f"x: {sm.dvl_x.value:.2f} → {sm.target_x.value:.2f}")
    print(f"y: {sm.dvl_y.value:.2f} → {sm.target_y.value:.2f}")
    print(f"z: {sm.dvl_z.value:.2f} → {sm.target_z.value:.2f}")

    # Log the current state and DVL readings
    new_entry = {
        'mode': mode.name if mode else "None",
        'state': getattr(mode, "state", "None") if mode else "None",
        'dvl_x': sm.dvl_x.value,
        'dvl_y': sm.dvl_y.value,
        'dvl_z': sm.dvl_z.value,
        'timestamp': time.time()
    }

    try:
        with open("log.yaml", "r") as f:
            logs = yaml.safe_load(f) or []
    except FileNotFoundError:
        logs = []

    logs.append(new_entry)
    with open("log.yaml", "w") as f:
        yaml.dump(logs, f)


def loop(mode):
    while shared_memory_object.running.value:
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), "r") as file:
            data = yaml.safe_load(file)
            course = data['course']
            test_delay = data[course]['delay']
            test_mult  = data[course]['mult']

        tx, ty, tz = get_targets_for_mode(mode.name, data, profile=course)

        sm = shared_memory_object
        sm.target_x.value, sm.target_y.value, sm.target_z.value = tx, ty, tz

        time.sleep(test_delay)

        # Move toward target with random drift
        max_step = max(1e-6, 0.25 * float(test_mult))
        k = 0.15
        sm.dvl_x.value = move_toward(sm.dvl_x.value, sm.target_x.value, k=k, max_step=max_step, noise_scale=0.05)
        sm.dvl_y.value = move_toward(sm.dvl_y.value, sm.target_y.value, k=k, max_step=max_step, noise_scale=0.05)
        sm.dvl_z.value = move_toward(sm.dvl_z.value, sm.target_z.value, k=k, max_step=max_step, noise_scale=0.05)
        
        # Check if mode is complete
        if hasattr(mode, "complete"):
            mode.complete = (
                approx_equal(sm.dvl_x.value, sm.target_x.value) and
                approx_equal(sm.dvl_y.value, sm.target_y.value) and
                approx_equal(sm.dvl_z.value, sm.target_z.value)
            )
        
        mode.loop()
        display(mode)
        
        # Transition to next mode if current is complete
        if getattr(mode, "complete", False):
            next_mode = getattr(mode, "next_mode", None)
            mode = next_mode
            if mode and hasattr(mode, "start"):
                mode.start()
        if mode is None:
            stop()
            break


def stop():
    shared_memory_object.running.value = 0


def main():
    make_list(mode_list)
    mode = mode_list[0]
    mode.start()
    loop(mode)


if __name__ == "__main__":
    print("RUN FROM LAUNCH")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, stopping program.")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
