import math
from typing import Iterator
from .variables import Variable, Level, Timer, State


class Module:
    """
    Base class for all DRS models and sub-components.
    Automatically registers variables and sub-modules upon assignment.
    """

    def __init__(self):
        self._variables = {}
        self._modules = {}
        self.parent = None

    def __setattr__(self, name, value):
        if isinstance(value, Variable):
            if not hasattr(self, "_variables"):
                raise AttributeError(
                    "cannot assign variable before Module.__init__() call"
                )
            self._variables[name] = value
        elif isinstance(value, Module) and name != "parent":
            if not hasattr(self, "_modules"):
                raise AttributeError(
                    "cannot assign module before Module.__init__() call"
                )
            self._modules[name] = value
            value.parent = self
        elif isinstance(value, list) and all(isinstance(v, Variable) for v in value):
            if not hasattr(self, "_variables"):
                raise AttributeError(
                    "cannot assign variable before Module.__init__() call"
                )
            for i, v in enumerate(value):
                self._variables[f"{name}_{i}"] = v

        super().__setattr__(name, value)

    def variables(self) -> Iterator[Variable]:
        """Recursively yield all variables in this module and sub-modules."""
        for var in self._variables.values():
            yield var
        for mod in self._modules.values():
            yield from mod.variables()

    def update_rates(self):
        """Override this to define the continuous dynamics (rates and thresholds)."""
        raise NotImplementedError("Module subclasses must implement update_rates()")

    # TODO: should this be here? is there a risk of incorrect resetting from this?
    def reset_variables(self):
        """Reset all variables to their default rate (0.0) and thresholds."""
        for var in self.variables():
            var.rate = 0.0
            var.upper_threshold = math.inf
            var.lower_threshold = -math.inf

    def check_transitions(self, trigger_var: Variable = None, is_upper: bool = True):
        """Override this to define discrete state changes."""
        # TODO: can we get rid of these checks? i think it can be said they all have a registry, im not sure about modes, but maybe we can have a default mode if no mode is set or something?
        if hasattr(self, "registry") and hasattr(self, "current_mode"):
            next_mode = self.registry.get_next_mode(
                self.current_mode.value, trigger_var, is_upper=is_upper
            )
            if next_mode:
                self.current_mode.value = next_mode

    def initialize_state(self):
        """Override this to set up initial state before the simulation starts."""
        pass

    # TODO: should this be required?
    def is_terminating_condition_met(self) -> bool:
        """Override this to define custom stopping conditions."""
        return False

    def record_statistics(self, current_time: float):
        """Default hook: If the module has telemetry initialized, take a snapshot."""
        if hasattr(self, "telemetry"):
            self.telemetry.snapshot(current_time)


class drs:
    """A namespace to mimic PyTorch's structure"""

    Module = Module
    Variable = Variable
    Level = Level
    Timer = Timer
    State = State
