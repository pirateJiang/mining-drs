import math
from dataclasses import dataclass, field

@dataclass
class CoreDRSConfig:
    """Base configuration required for all DRS models."""
    replication_length: float = math.inf
    base_time_units: str = "days"
    
@dataclass
class MiningDRSConfig(CoreDRSConfig):
    """Specific configuration for mining operations."""
    target_ore_stock_level: float = 60000.0
    total_ore_to_extract: float = field(default_factory=lambda: float('inf'))
