import math


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
