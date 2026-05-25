from enum import Enum
from typing import Callable, Dict, Any


# TODO: what does this actually do? like where is it used? why is it useful? is it too specific?
class StateMachine:
    """
    Maps specific modes (Enums) to Python callable functions, replacing
    legacy string evaluation with structured Command Patterns.
    
    Note: In the Arena Excel examples, this maps to the concept of "Assignment Sequences".
    """

    def __init__(self):
        self.sequences: Dict[Enum, Callable] = {}
        self.transitions = {}

    def register(self, mode: Enum, func: Callable):
        """Register a callable sequence for a given mode."""
        self.sequences[mode] = func

    def apply_rates(self, mode: Enum):
        """
        Execute the registered sequence for the current mode.
        Fails fast if the mode is not registered.
        """
        if mode not in self.sequences:
            raise ValueError(f"Fail Fast: Sequence for mode {mode} does not exist!")

        # Call the python function cleanly
        return self.sequences[mode]()

    def register_transition(
        self, source: Enum, trigger: Any, target: Any
    ):
        """
        Register a transition rule.
        
        Args:
            source: The mode to transition from.
            trigger: A tuple of (Variable, is_upper_boolean), usually provided by var.lower_bound or var.upper_bound.
            target: The mode (or callable returning a mode/None) to transition to.
        """
        if not isinstance(trigger, tuple) or len(trigger) != 2:
            raise ValueError("Trigger must be a tuple of (Variable, is_upper_bool). Use var.upper_bound or var.lower_bound.")
            
        trigger_var, is_upper = trigger
        key = (source, trigger_var, is_upper)
        self.transitions[key] = target

    def get_next_mode(
        self,
        current_mode: Enum,
        trigger: Any,
        is_upper: bool = True,
    ):
        """
        Get the next mode for a given trigger in the current mode.
        """
        key = (current_mode, trigger, is_upper)
        if key in self.transitions:
            nxt = self.transitions[key]
            if callable(nxt):
                return nxt()
            return nxt
        return None
