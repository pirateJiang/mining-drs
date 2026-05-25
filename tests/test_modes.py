import pytest
from enum import Enum
from mining_drs.modes import StateMachine


class MockMode(Enum):
    NORMAL = "Normal"
    MAINTENANCE = "Maintenance"
    CONTINGENCY = "Contingency"


def test_sequence_registry_registration():
    registry = StateMachine()

    context = {}
    def normal_sequence():
        context["status"] = "running_normally"
        return context["status"]

    registry.register(MockMode.NORMAL, normal_sequence)

    assert MockMode.NORMAL in registry.sequences
    assert registry.sequences[MockMode.NORMAL] == normal_sequence


def test_sequence_registry_execution():
    registry = StateMachine()

    context = {"durability": 50}
    
    def maintenance_sequence():
        context["durability"] += 10
        return True

    registry.register(MockMode.MAINTENANCE, maintenance_sequence)

    result = registry.apply_rates(MockMode.MAINTENANCE)

    assert result is True
    assert context["durability"] == 60


def test_sequence_registry_fails_fast_on_missing_mode():
    registry = StateMachine()

    # We never registered Contingency mode
    with pytest.raises(
        ValueError,
        match="Fail Fast: Sequence for mode MockMode.CONTINGENCY does not exist!",
    ):
        registry.apply_rates(MockMode.CONTINGENCY)
