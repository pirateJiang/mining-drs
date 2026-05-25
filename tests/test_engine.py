import pytest
from mining_drs.engine import DRSEngine

class MockSimulationEngine(DRSEngine):
    def __init__(self, target_ticks: int):
        self.target_ticks = target_ticks
        self.current_ticks = 0
        self.time = 0.0
        self.log = []

    def initialize_state(self):
        self.log.append("init")

    def is_terminating_condition_met(self) -> bool:
        return self.current_ticks >= self.target_ticks

    def calculate_time_to_next_threshold(self) -> float:
        self.log.append("calc_dt")
        return 1.0

    def advance_time(self, dt: float):
        self.log.append("advance")
        self.time += dt

    def check_and_trigger_thresholds(self):
        self.log.append("check")

    def record_statistics(self):
        self.log.append("record")
        self.current_ticks += 1


def test_engine_execution_order():
    engine = MockSimulationEngine(target_ticks=1)
    engine.run()
    
    expected_log = [
        "init",
        "calc_dt",
        "advance",
        "check",
        "record"
    ]
    assert engine.log == expected_log
    assert engine.time == 1.0


def test_engine_multiple_ticks():
    engine = MockSimulationEngine(target_ticks=3)
    engine.run()
    
    assert engine.time == 3.0
    assert engine.current_ticks == 3
    # Check that init happens exactly once
    assert engine.log.count("init") == 1
    # Check that the loop runs 3 times
    assert engine.log.count("advance") == 3


def test_engine_negative_dt_raises_error():
    class BadEngine(MockSimulationEngine):
        def calculate_time_to_next_threshold(self) -> float:
            return -1.0
            
    engine = BadEngine(target_ticks=1)
    
    with pytest.raises(ValueError, match="Time delta \\(dt\\) cannot be negative"):
        engine.run()
