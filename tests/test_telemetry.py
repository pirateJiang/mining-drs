import pytest
from mining_drs.telemetry import Telemetry, PANDAS_AVAILABLE
from mining_drs.variables import Level, Timer, Tracker

class MockEngine:
    def __init__(self):
        self.variables = [
            Level("ore_stock", 1000.0),
            Timer("runtime", 0.0),
            Tracker("trucks_dispatched", 5)
        ]

def test_telemetry_snapshot():
    engine = MockEngine()
    telemetry = Telemetry(engine)
    
    # Take a snapshot at t=1.0
    telemetry.snapshot(current_time=1.0)
    
    # Engine updates
    engine.variables[0].update(2.0) # Ore stock changes to 1000 + (0 * 2) = 1000.0 (rate is 0)
    engine.variables[0].rate = 50.0
    engine.variables[0].update(1.0) # Ore stock changes to 1050.0
    engine.variables[1].update(1.0) # Runtime changes to 1.0
    engine.variables[2].value = 6   # Trucks to 6
    
    # Take a snapshot at t=2.0
    telemetry.snapshot(current_time=2.0)
    
    history = telemetry.get_raw_history()
    
    assert len(history) == 2
    
    # Verify snapshot 1
    assert history[0]['time'] == 1.0
    assert history[0]['ore_stock'] == 1000.0
    assert history[0]['runtime'] == 0.0
    assert history[0]['trucks_dispatched'] == 5
    
    # Verify snapshot 2
    assert history[1]['time'] == 2.0
    assert history[1]['ore_stock'] == 1050.0
    assert history[1]['runtime'] == 1.0
    assert history[1]['trucks_dispatched'] == 6

def test_telemetry_to_dataframe():
    engine = MockEngine()
    telemetry = Telemetry(engine)
    telemetry.snapshot(current_time=0.0)
    
    if PANDAS_AVAILABLE:
        import pandas as pd
        df = telemetry.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert list(df.columns) == ['time', 'ore_stock', 'runtime', 'trucks_dispatched']
    else:
        with pytest.raises(ImportError, match="pandas is required"):
            telemetry.to_dataframe()
