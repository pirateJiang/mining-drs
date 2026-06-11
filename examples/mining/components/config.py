import math
from dataclasses import dataclass


@dataclass
class BaseDualStockpileConfig:
    replication_length: float = math.inf
    """
    Shared configuration for dual-stockpile surging mine operations.
    Contains mass-balance and scheduling parameters common to all models.
    """

    # Mass Balance Parameters
    target_ore_stock_level: float = 60000.0
    total_ore_to_extract: float = 6600000.0
    ore_to_be_extracted_during_warming_period: float = 600000.0
    critical_ore2_level: float = 20400.0

    # Timing / Scheduling
    duration_of_production_campaigns: float = 34.0
    duration_of_shutdowns: float = 1.0
    duration_of_contingency_segments: float = 1.0

    # Helper Constants
    stockout_epsilon: float = 1e-9


@dataclass
class ConcentratorConfig(BaseDualStockpileConfig):
    """
    Configuration for Navarra (2019): Base-metal flotation concentrator.
    Attribute: Ore Grade (%)
    """

    mean_grade: float = 30.0
    std_dev_grade: float = 5.0
    grade_percentage_scale: float = 100.0

    # Generator Parameters
    min_ore_mass: float = 30000.0
    max_ore_mass: float = 50000.0
    prob_new_facies: float = 0.3  # NOTE Arena example incorrectly set this to 30.
    variation_same_facies: float = 1.0

    # Milling rates specific to the Concentrator paper
    mode_a_ore1_milling_rate: float = 3600.0
    mode_a_ore2_milling_rate: float = 2400.0
    mode_a_contingency_ore1_milling_rate: float = 3900.0
    mode_b_ore1_milling_rate: float = 4600.0
    mode_b_ore2_milling_rate: float = 800.0
    mode_b_contingency_ore2_milling_rate: float = 2500.0


@dataclass
class CyanidationConfig(BaseDualStockpileConfig):
    """
    Configuration for Órdenes (2026): Au-Ag cyanidation leaching plant.
    Attribute: Cyanide Consumption (kg/t)
    """

    # Using real historical values from Table 2 of the paper
    mean_cyanide_consumption: float = 2.53
    std_dev_cyanide_consumption: float = 1.26

    # Generator Parameters (mass per block)
    min_ore_mass: float = 30000.0
    max_ore_mass: float = 50000.0

    # Milling rates specific to Stage 1 of the Cyanidation paper (Table 4)
    # (If they are the same as Navarra 2019 in your specific test case, you can leave them as is,
    # but separating them allows you to easily add Stage 2 modes later!)
    mode_a_ore1_milling_rate: float = 400.0
    mode_a_ore2_milling_rate: float = 1600.0
    mode_a_contingency_ore1_milling_rate: float = 1300.0
    mode_b_ore1_milling_rate: float = 765.0
    mode_b_ore2_milling_rate: float = 935.0
    mode_b_contingency_ore2_milling_rate: float = 850.0

    # Stage 2 Transition
    stage_2_start_period: int = 26

    # Milling rates specific to Stage 2 (Configurations C & D)
    # Mode C (Productive Mode): 2750 t/day at 40% Sulphide (Ore 1) / 60% Oxide (Ore 2)
    mode_c_ore1_milling_rate: float = 1100.0
    mode_c_ore2_milling_rate: float = 1650.0
    mode_c_contingency_ore1_milling_rate: float = 1790.0

    # Mode D (Recuperative Mode): 2340 t/day at 55% Sulphide (Ore 1) / 45% Oxide (Ore 2)
    mode_d_ore1_milling_rate: float = 1287.0
    mode_d_ore2_milling_rate: float = 1053.0
    mode_d_contingency_ore2_milling_rate: float = 1170.0

    # Average Cyanide Consumption per mode (kg/t)
    mode_a_avg_cyanide: float = 1.9
    mode_a_contingency_avg_cyanide: float = 3.2
    mode_b_avg_cyanide: float = 2.3
    mode_b_contingency_avg_cyanide: float = 1.6
    mode_c_avg_cyanide: float = 2.3
    mode_c_contingency_avg_cyanide: float = 3.2
    mode_d_avg_cyanide: float = 2.5
    mode_d_contingency_avg_cyanide: float = 1.6
