import math
from typing import Tuple, Optional
from .variables import Variable
from .module import Module


class DRSEngine:
    """
    The runner that manages the external simulation loop.
    It takes a DRS module, steps time forward to the next threshold,
    and asks the module to process transitions.
    """

    def __init__(self, model: Module):
        self.model = model
        self.current_time = 0.0

    def run(self, max_time: Optional[float] = None):
        """The main simulation loop."""

        # Initialize state via standard OO contract
        self.model.initialize_state()

        while True:
            # Check standard OO contract terminating condition
            if self.model.is_terminating_condition_met():
                break

            # Check standard time-based terminating condition
            if max_time is not None and self.current_time >= max_time:
                break

            # 1. Ask the model to set its current rates based on its state
            self.model.reset_variables()
            self.model.update_rates()

            # 2. Look at all variables to find the closest threshold
            current_variables = list(self.model.variables())
            dt, trigger_var, is_upper = self.calculate_min_dt(current_variables)

            # Prevent infinite loops
            if dt < 0:
                raise ValueError("Time delta (dt) cannot be negative.")

            # 3. Advance time
            self.current_time += dt
            for var in current_variables:
                var.update(dt)

            # 4. Ask the model if any discrete transitions trigger
            self.model.check_transitions(trigger_var, is_upper)

            # 5. Record statistics blindly via standard OO contract hook
            self.model.record_statistics(self.current_time)

    def calculate_min_dt(
        self, variables: list[Variable]
    ) -> Tuple[float, Optional[Variable], bool]:
        """
        Determine the time step (dt) to the next event/threshold.
        Returns a tuple of (min_dt, trigger_var, is_upper).
        """
        min_dt = math.inf
        trigger_var = None
        is_upper = True

        for var in variables:
            dt_for_var = math.inf
            var_is_upper = True

            if var.rate > 0:
                dt_for_var = (var.upper_threshold - var.value) / var.rate
            elif var.rate < 0:
                dt_for_var = (var.value - var.lower_threshold) / abs(var.rate)
                var_is_upper = False

            if 1e-9 < dt_for_var < min_dt:
                min_dt = dt_for_var
                trigger_var = var
                is_upper = var_is_upper

        if min_dt == math.inf:
            return 1.0, None, True

        return min_dt, trigger_var, is_upper
