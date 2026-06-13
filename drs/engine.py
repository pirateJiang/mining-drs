import math
from typing import Tuple, Optional
from .variables import Variable
from .module import Module
from .execution_context import ExecutionContext


class DRSEngine:
    """
    The runner that manages the external simulation loop.
    It takes a DRS module, steps time forward to the next threshold,
    and asks the module to process transitions.
    """

    def __init__(
        self,
        model: Module,
        max_step_size: float = 0.5,
        max_deadlock_steps: int = 20,
    ):
        self.model = model
        self.current_time = 0.0
        self.max_step_size = max_step_size
        self.max_deadlock_steps = max_deadlock_steps

    def run(self, max_time: Optional[float] = None):
        """The main simulation loop."""

        ExecutionContext.push(self.model)
        self.model.initialize_state()
        ExecutionContext.pop()

        last_trigger_var = None
        consecutive_zero_dt_count = 0

        while True:
            if self.model.is_terminating_condition_met():
                break

            if max_time is not None and self.current_time >= max_time:
                break

            self.model.zero_rates()
            self.model()

            self.model._run_post_step_hooks(self.current_time)

            current_variables = list(self.model.variables())
            dt, trigger_var, is_upper = self.calculate_min_dt(current_variables)

            dt = min(dt, self.max_step_size)

            if max_time is not None:
                dt = min(dt, max_time - self.current_time)

            if dt == 0.0:
                consecutive_zero_dt_count += 1
                if consecutive_zero_dt_count > self.max_deadlock_steps:
                    state_dump = "\n--- Engine State at Deadlock ---\n"
                    for v in current_variables:
                        rate_val = getattr(v, "rate", "N/A")
                        lower_val = getattr(v, "lower_threshold", "N/A")
                        upper_val = getattr(v, "upper_threshold", "N/A")
                        state_dump += f"{v.name}: value={v.value}, rate={rate_val}, bounds=[{lower_val}, {upper_val}]\n"

                    raise RuntimeError(
                        f"DeadlockError: Maximum consecutive zero-time steps ({self.max_deadlock_steps}) reached. "
                        f"The simulation is ping-ponging between states without advancing time. "
                        f"Last trigger: '{trigger_var.name if trigger_var else 'None'}' "
                        f"(value={trigger_var.value if trigger_var else 'None'}, "
                        f"rate={getattr(trigger_var, 'rate', 'N/A') if trigger_var else 'None'}).\n{state_dump}"
                    )
                last_trigger_var = trigger_var
            else:
                consecutive_zero_dt_count = 0
                last_trigger_var = None

            if dt < 0:
                raise ValueError("Time delta (dt) cannot be negative.")

            self.current_time += dt
            for var in current_variables:
                if hasattr(var, "update"):
                    var.update(dt)

        self.model._run_post_step_hooks(self.current_time)

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

            if hasattr(var, "rate"):
                rate = var.rate
                if rate > 0:
                    dt_for_var = (var.upper_threshold - var.value) / rate
                elif rate < 0:
                    dt_for_var = (var.value - var.lower_threshold) / abs(rate)
                    var_is_upper = False

            if -1e-12 <= dt_for_var < min_dt:
                min_dt = max(0.0, dt_for_var)
                trigger_var = var
                is_upper = var_is_upper

        if min_dt == math.inf:
            return 1.0, None, True

        return min_dt, trigger_var, is_upper
