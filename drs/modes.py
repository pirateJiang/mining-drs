from enum import Enum
from typing import Callable, Dict, Any

# mining_drs/modes.py (NEW)
from abc import ABC, abstractmethod
from typing import Optional, Union
from drs.module import drs

"""
Like a pytorch optimizer.
Instead of updating weights we update rates and other variables here.
"""


class RequireDecision(Exception):
    """A signal flag and engine interrupt for when the simulation requires external control."""

    pass


class OperatingMode(ABC):
    def __eq__(self, other):
        if not isinstance(other, OperatingMode):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    @property
    @abstractmethod
    def id(self) -> int:
        """The discrete integer action for the Gym environment."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """String representation for plotting/telemetry."""
        pass

    @abstractmethod
    def is_valid_start(self, model: drs.Module) -> bool:
        """Do the conditions of our system allow for this mode to be entered?
        Useful for Action Masking: Can the RL agent choose this mode right now?
        """
        pass

    # TODO: do we want this to return modes or should it basically just return True if it ended and then the controller should pick the mode from there?
    @abstractmethod
    def check_end_conditions(
        self, model: drs.Module
    ) -> Union[Optional["OperatingMode"], RequireDecision]:
        """Preemption: Does the current state force a transition to a different mode? Does it require a decision from a controller as to our next mode?"""
        pass

    @abstractmethod
    def apply_dynamics(self, model: drs.Module):
        """Physics: Sets the drs.Variable rates and thresholds for this specific mode."""
        pass
