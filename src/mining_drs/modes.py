from enum import Enum
from typing import Callable, Dict, Any


class MiningMode(Enum):
    """Enumeration of operational modes for a mining simulation."""

    NORMAL = "Normal"
    MAINTENANCE = "Maintenance"
    CONTINGENCY = "Contingency"


class SequenceRegistry:
    """
    Maps specific modes (Enums) to Python callable functions, replacing
    legacy string evaluation with structured Command Patterns.
    """

    def __init__(self):
        self.sequences: Dict[Enum, Callable] = {}

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
