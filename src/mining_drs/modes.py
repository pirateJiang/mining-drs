from enum import Enum
from typing import Callable, Dict, Any


# TODO: what does this actually do? like where is it used? why is it useful? is it too specific?
class SequenceRegistry:
    """
    Maps specific modes (Enums) to Python callable functions, replacing
    legacy string evaluation with structured Command Patterns.
    """

    def __init__(self):
        self.sequences: Dict[Enum, Callable] = {}
        self.transitions = {}

    def register(self, mode: Enum, func: Callable):
        """Register a callable sequence for a given mode."""
        self.sequences[mode] = func

    def execute(self, mode: Enum, context: Any = None):
        """
        Execute the registered sequence for the current mode.
        Fails fast if the mode is not registered.
        """
        if mode not in self.sequences:
            raise ValueError(f"Fail Fast: Sequence for mode {mode} does not exist!")

        # Call the python function cleanly
        return self.sequences[mode](context)

    def register_transition(
        self, current_mode: Enum, next_mode: Any, trigger: Any, is_upper: bool = True
    ):
        """
        Register a transition from a current mode to a next mode based on a trigger.
        next_mode can be an Enum or a Callable that returns an Enum.
        """
        key = (current_mode, trigger, is_upper)
        self.transitions[key] = next_mode

    def get_next_mode(
        self,
        current_mode: Enum,
        trigger: Any,
        is_upper: bool = True,
        context: Any = None,
    ):
        """
        Get the next mode for a given trigger in the current mode.
        """
        key = (current_mode, trigger, is_upper)
        if key in self.transitions:
            nxt = self.transitions[key]
            if callable(nxt):
                return nxt(context)
            return nxt
        return None
