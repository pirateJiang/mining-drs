import pytest
import math
from drs.engine import DRSEngine
from drs.module import Module
from drs.variables import Level

class MockModule(Module):
    def __init__(self, target_ticks: int):
        super().__init__()
        self.target_ticks = target_ticks
        self.current_ticks = 0
        self.log = []
        self.var = Level("dummy", 0.0, 1.0)
        self.var.upper_threshold = 1.0

    def variables(self):
        yield self.var

    def initialize_state(self):
        self.log.append("init")

    def is_terminating_condition_met(self) -> bool:
        return self.current_ticks >= self.target_ticks

    def update_rates(self):
        self.log.append("update_rates")

    def check_transitions(self, trigger_var, is_upper):
        self.log.append("check")
        # reset for next tick
        self.var.value = 0.0

    def record_statistics(self, current_time):
        self.log.append("record")
        self.current_ticks += 1

def test_engine_execution_order():
    model = MockModule(target_ticks=1)
    engine = DRSEngine(model)
    engine.run()
    
    expected_log = [
        "init",
        "update_rates",
        "check",
        "record"
    ]
    assert model.log == expected_log
    assert engine.current_time == 1.0

def test_engine_multiple_ticks():
    model = MockModule(target_ticks=3)
    engine = DRSEngine(model)
    engine.run()
    
    assert engine.current_time == 3.0
    assert model.current_ticks == 3
    assert model.log.count("init") == 1
    assert model.log.count("update_rates") == 3

def test_engine_negative_dt_raises_error():
    model = MockModule(target_ticks=1)
    engine = DRSEngine(model)
    
    # Mock the engine's dt calculation to force a negative dt
    engine.calculate_min_dt = lambda variables: (-1.0, None, True)
    
    with pytest.raises(ValueError, match="Time delta \\(dt\\) cannot be negative."):
        engine.run()

