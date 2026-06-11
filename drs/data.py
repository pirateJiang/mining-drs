from typing import Dict
from dataclasses import dataclass, field


@dataclass
class Flow:
    """An ephemeral bundle of continuous DRS rates passed between modules."""

    rate: float
    attributes: Dict[str, float] = field(default_factory=dict)

    def __mul__(self, fraction: float) -> "Flow":
        return Flow(
            rate=self.rate * fraction,
            attributes={k: v * fraction for k, v in self.attributes.items()},
        )

    def __rmul__(self, fraction: float) -> "Flow":
        return self.__mul__(fraction)
