from dataclasses import dataclass

@dataclass
class TargetRates:
    """Requested production rates returned by the Controller."""

    extraction_rate: float
    ore1_milling_rate: float
    ore2_milling_rate: float
