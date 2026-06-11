from typing import List, Dict, Optional

from drs.module import drs


class Stockpile(drs.Module):
    def __init__(
        self,
        name: str,
        expected_attributes: List[str],
        initial_mass: float = 0.0,
        initial_attributes: Optional[Dict[str, float]] = None,
    ):
        super().__init__()
        self.name = name
        self.expected_attributes = expected_attributes

        self.mass = drs.Level(f"{name}_mass", initial_value=initial_mass)
        self.actual_outflow = drs.Variable(f"{name}_actual_outflow", 0.0)

        initial_attributes = initial_attributes or {}
        for attr in expected_attributes:
            setattr(self, attr, drs.Level(f"{name}_{attr}", initial_value=initial_attributes.get(attr, 0.0)))

    def current_concentration(self, attr: str) -> float:
        level = getattr(self, attr, None)
        if level is None:
            return 0.0
        return level.value / max(1e-6, self.mass.value)

    def forward(self, requested_outflow_rate: float) -> float:
        inflow = self.mass.rate
        actual_outflow = requested_outflow_rate
        if self.mass.value <= 1e-6:
            actual_outflow = min(actual_outflow, inflow)

        for attr in self.expected_attributes:
            level = getattr(self, attr)
            level.rate = level.rate - actual_outflow * self.current_concentration(attr)

        self.mass.rate = self.mass.rate - actual_outflow

        if self.mass.rate < 0:
            self.mass.lower_threshold = 0.0
            for attr in self.expected_attributes:
                getattr(self, attr).lower_threshold = 0.0

        self.actual_outflow.value = actual_outflow
        return actual_outflow
