from typing import List, Dict, Optional
from drs.data import Flow
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

    def forward(self, inflow: Flow, requested_outflow_rate: float) -> Flow:
        """Process inflow, apply conservation, and return actual achievable outflow."""
        # Prevent deadlock: clamp outflow if stockpile is empty
        actual_outflow = requested_outflow_rate
        if self.mass.value <= 1e-6:
            actual_outflow = min(actual_outflow, inflow.rate)

        outflow = Flow(
            rate=actual_outflow,
            attributes={
                attr: actual_outflow * self.current_concentration(attr)
                for attr in self.expected_attributes
            },
        )

        self.mass.rate = inflow.rate - outflow.rate
        for attr in self.expected_attributes:
            level = getattr(self, attr)
            level.rate = inflow.attributes.get(attr, 0.0) - outflow.attributes.get(attr, 0.0)

        # CRITICAL FIX: Tell the engine to calculate a dt to stop exactly at 0.0
        if self.mass.rate < 0:
            self.mass.lower_threshold = 0.0
            for attr in self.expected_attributes:
                level = getattr(self, attr)
                level.lower_threshold = 0.0

        return outflow
