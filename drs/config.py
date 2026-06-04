import math
from dataclasses import dataclass


@dataclass
class CoreDRSConfig:
    """Base configuration required for all DRS models."""

    replication_length: float = math.inf
    base_time_units: str = "days"
    # TODO: is there more I should add?
