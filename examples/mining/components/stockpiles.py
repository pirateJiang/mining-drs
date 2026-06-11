from typing import List, Dict, Optional, Tuple
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

        initial_attributes = initial_attributes or {}
        for attr in expected_attributes:
            setattr(self, attr, drs.Level(f"{name}_{attr}", initial_value=initial_attributes.get(attr, 0.0)))

    def current_concentration(self, attr: str) -> float:
        level = getattr(self, attr, None)
        if level is None:
            return 0.0
        safe_mass = max(1e-6, self.mass.value)
        return level.value / safe_mass

    def forward(self, inflow_rate: float, inflow_attributes: dict, requested_outflow_rate: float) -> Tuple[float, dict]:
        """Process inflow, apply conservation, and return (actual_outflow_rate, outflow_attributes)."""
        actual_outflow = requested_outflow_rate
        if self.mass.value <= 1e-6:
            actual_outflow = min(actual_outflow, inflow_rate)

        outflow_attributes = {
            attr: actual_outflow * self.current_concentration(attr)
            for attr in self.expected_attributes
        }

        self.mass.rate = inflow_rate - actual_outflow
        for attr in self.expected_attributes:
            level = getattr(self, attr)
            level.rate = inflow_attributes.get(attr, 0.0) - outflow_attributes.get(attr, 0.0)

        if self.mass.rate < 0:
            self.mass.lower_threshold = 0.0
            for attr in self.expected_attributes:
                level = getattr(self, attr)
                level.lower_threshold = 0.0

        return (actual_outflow, outflow_attributes)
