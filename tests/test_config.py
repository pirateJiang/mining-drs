import math
from mining_drs.config import CoreDRSConfig, MiningDRSConfig


def test_core_drs_config_defaults():
    config = CoreDRSConfig()
    assert config.replication_length == math.inf
    assert config.base_time_units == "days"


def test_core_drs_config_overrides():
    config = CoreDRSConfig(replication_length=100.0, base_time_units="hours")
    assert config.replication_length == 100.0
    assert config.base_time_units == "hours"


def test_mining_drs_config_defaults():
    config = MiningDRSConfig()
    # Check inherited defaults
    assert config.replication_length == math.inf
    assert config.base_time_units == "days"

    # Check specific defaults
    assert config.target_ore_stock_level == 60000.0
    assert config.total_ore_to_extract == math.inf


def test_mining_drs_config_overrides():
    config = MiningDRSConfig(
        replication_length=365.0,
        target_ore_stock_level=120000.0,
        total_ore_to_extract=500000.0,
    )
    assert config.replication_length == 365.0
    assert config.base_time_units == "days"  # Kept default
    assert config.target_ore_stock_level == 120000.0
    assert config.total_ore_to_extract == 500000.0
