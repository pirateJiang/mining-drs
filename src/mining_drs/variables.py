import math
from typing import Any


class Variable:
    """Base class for all domain variables."""

    def __init__(self, name: str, initial_value: float = 0.0, rate: float = 0.0):
        self.name = name
        self.value = initial_value
        self.rate = rate
        self.upper_threshold = math.inf
        self.lower_threshold = -math.inf

    def update(self, dt: float):
        """Update the value based on the current rate and a time delta."""
        self.value += self.rate * dt

    @property
    def upper_bound(self):
        """Returns a tuple for use as a trigger: (self, True)"""
        return (self, True)

    @property
    def lower_bound(self):
        """Returns a tuple for use as a trigger: (self, False)"""
        return (self, False)


class Level(Variable):
    """A variable that accumulates over time based on a rate."""

    def __init__(self, name: str, initial_value: float = 0.0, rate: float = 0.0):
        super().__init__(name, initial_value, rate)


class Timer(Level):
    """A specialized level used to track time, typically with a rate of 1.0 or -1.0."""

    def __init__(self, name: str, initial_value: float = 0.0, rate: float = 1.0):
        super().__init__(name, initial_value, rate)

    def reset(self):
        """Reset the timer to 0.0."""
        self.value = 0.0


class State(Variable):
    """
    Tracks categorical or discrete states (Enums, strings, booleans). 
    The engine ignores it for time-stepping, but Telemetry auto-records it.
    """
    def __init__(self, name: str, initial_value: Any):
        super().__init__(name, initial_value)
        # Force rates to 0 and thresholds to infinity so the Engine ignores it
        self.rate = 0.0
        self.upper_threshold = float('inf')
        self.lower_threshold = float('-inf')

    def update(self, dt: float):
        pass # Discrete states do not integrate over continuous time
