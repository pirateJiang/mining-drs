import pytest
from drs.modes import OperatingMode, RequireDecision
from drs.module import drs
from typing import Union, Optional

class MockMode(OperatingMode):
    def __init__(self, mode_id: int, name: str):
        self._id = mode_id
        self._name = name
        
    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module) -> Union[Optional["OperatingMode"], RequireDecision]:
        return None

    def apply_dynamics(self, model: drs.Module):
        pass

def test_operating_mode_equality():
    mode1 = MockMode(1, "Mode 1")
    mode1_copy = MockMode(1, "Mode 1 Copy")
    mode2 = MockMode(2, "Mode 2")

    assert mode1 == mode1_copy
    assert mode1 != mode2
    assert mode1 != "Not a mode"

def test_operating_mode_hashing():
    mode1 = MockMode(1, "Mode 1")
    mode1_copy = MockMode(1, "Mode 1 Copy")
    
    # Modes with the same ID should hash to the same value
    mode_set = {mode1, mode1_copy}
    assert len(mode_set) == 1
