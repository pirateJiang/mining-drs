from typing import Iterator
from .variables import Variable, Level, Timer


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

    def check_transitions(self, trigger_var: Variable = None, is_upper: bool = True):
        """Override this to define discrete state changes."""
        pass

    def initialize_state(self):
        """Override this to set up initial state before the simulation starts."""
        pass

    # TODO: should this be required?
    def is_terminating_condition_met(self) -> bool:
        """Override this to define custom stopping conditions."""
        return False

    def record_statistics(self, current_time: float):
        """Override this to save data or ping telemetry at each tick."""
        pass


class drs:
    """A namespace to mimic PyTorch's structure"""

    Module = Module
    Variable = Variable
    Level = Level
    Timer = Timer
