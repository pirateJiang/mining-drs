import pytest
from mining_drs.modes import MiningMode, SequenceRegistry

def test_sequence_registry_registration():
    registry = SequenceRegistry()
    
    def normal_sequence(context):
        context["status"] = "running_normally"
        return context["status"]

    registry.register(MiningMode.NORMAL, normal_sequence)
    
    assert MiningMode.NORMAL in registry.sequences
    assert registry.sequences[MiningMode.NORMAL] == normal_sequence

def test_sequence_registry_execution():
    registry = SequenceRegistry()
    
    def maintenance_sequence(context):
        context["durability"] += 10
        return True

    registry.register(MiningMode.MAINTENANCE, maintenance_sequence)
    
    context = {"durability": 50}
    result = registry.execute(MiningMode.MAINTENANCE, context)
    
    assert result is True
    assert context["durability"] == 60

def test_sequence_registry_fails_fast_on_missing_mode():
    registry = SequenceRegistry()
    
    # We never registered Contingency mode
    with pytest.raises(ValueError, match="Fail Fast: Sequence for mode MiningMode.CONTINGENCY does not exist!"):
        registry.execute(MiningMode.CONTINGENCY, context={})
