from dataclasses import dataclass
from mining_drs.config import CoreDRSConfig


@dataclass
class MiningDRSConfig(CoreDRSConfig):
    """Specific configuration for mining operations."""

    target_ore_stock_level: float = 60000.0
    total_ore_to_extract: float = 6600000.0
    ore_to_be_extracted_during_warming_period: float = 600000.0
    duration_of_production_campaigns: float = 34.0
    duration_of_shutdowns: float = 1.0
    critical_ore2_level: float = 20400.0
    duration_of_contingency_segments: float = 1.0

    mode_a_ore1_milling_rate: float = 3600.0
    mode_a_ore2_milling_rate: float = 2400.0
    mode_a_contingency_ore1_milling_rate: float = 3900.0
    mode_b_ore1_milling_rate: float = 4600.0
    mode_b_ore2_milling_rate: float = 800.0
    mode_b_contingency_ore2_milling_rate: float = 2500.0
    
    # Geostatistical Parameters
    min_ore_mass: float = 30000.0
    max_ore_mass: float = 50000.0
    prob_new_facies: float = 0.3
    mean_grade_new_facies: float = 30.0
    std_dev_new_facies: float = 5.0
    variation_same_facies: float = 1.0
