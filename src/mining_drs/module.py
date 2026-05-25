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
        """Recursively yield all variables in this module and sub-modules without duplicates."""
        seen = set()

        def _get_vars(module):
            for var in module._variables.values():
                var_id = id(var)
                if var_id not in seen:
                    seen.add(var_id)
                    yield var
            for mod in module._modules.values():
                yield from _get_vars(mod)

        yield from _get_vars(self)

    def update_rates(self):
        """Override this to define the continuous dynamics (rates and thresholds)."""
        raise NotImplementedError("Module subclasses must implement update_rates()")

    def zero_rates(self):
        """Zero out rates and remove thresholds for all variables before the next rate update."""
        for var in self.variables():
            var.rate = 0.0
            var.upper_threshold = math.inf
            var.lower_threshold = -math.inf

    def check_transitions(self, trigger_var: Variable = None, is_upper: bool = True):
        """Override this to define discrete state changes. Explicitly delegate to sub-modules or registries here."""
        pass

    def initialize_state(self):
        """Override this to set up initial state before the simulation starts."""
        pass

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
