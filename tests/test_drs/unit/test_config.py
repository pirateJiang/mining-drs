import math
from drs.config import CoreDRSConfig


def test_core_drs_config_defaults():
    config = CoreDRSConfig()
    assert config.replication_length == math.inf
    assert config.base_time_units == "days"


def test_core_drs_config_overrides():
    config = CoreDRSConfig(replication_length=100.0, base_time_units="hours")
    assert config.replication_length == 100.0
    assert config.base_time_units == "hours"
