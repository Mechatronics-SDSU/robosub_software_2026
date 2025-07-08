from modules.motors.MotorWrapper            import MotorWrapper
import yaml
import os

class HierarchicalStateMachine:
    def __init__(self):

        self.filename = "states.yaml"
        self.load_states()
        
        # self.motor_wrapper = MotorWrapper()

    def load_states(self):
        """
        Load the HFSM YAML file into states
        """
        full_path = os.path.join(os.path.dirname(__file__), self.filename)

        try:
            with open(full_path, 'r') as file:
                self.states = yaml.safe_load(file)
                print(f"States loaded successfully from {full_path}")
        except FileNotFoundError:
            print(f"❌ Error: The file {full_path} does not exist.")
            self.states = {}
        except yaml.YAMLError as e:
            print(f"❌ YAML parsing error in {full_path}:\n{e}")
            self.states = {}
        except Exception as e:
            print(f"❌ Unexpected error while loading {full_path}:\n{e}")
            self.states = {}

    def get_state(self, state_name):
        """
        Get the state by name.
        """
        return self.states.get(state_name, None)
    
    def get_state_action(self, state_name, action_name):
        """
        Get the action for a specific state.
        """
        state = self.get_state(state_name)
        if state:
            return state.get('actions', {}).get(action_name, None)
        return None
    
    def get_next_state(self, current_state, event):
        """
        Get the next state based on the current state and event.
        """
        transitions = self.states.get(current_state, {}).get('transitions', {})
        return transitions.get(event, None)


def main():
    """
    Main function to run the hierarchical state machine.
    """
    hsm = HierarchicalStateMachine()
    print("Hierarchical State Machine initialized.")
    # Example usage

    print("Current States:")
    print(hsm.states)

    # Example of running the state machine
    current_state = "Gate"
    print(f"Current State: {current_state}")
    print(hsm.get_state(current_state))
    print(hsm.get_next_state(current_state, 'open'))

    
if __name__ == "__main__":
    main()
    