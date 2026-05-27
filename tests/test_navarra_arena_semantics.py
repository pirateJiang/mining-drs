import math
import sys
from pathlib import Path


NAVARRA_STANDARD = Path(__file__).resolve().parents[1] / "examples" / "navarra" / "standard"
if str(NAVARRA_STANDARD) not in sys.path:
    sys.path.insert(0, str(NAVARRA_STANDARD))

from example_mine import ExampleMineModel, MineMode
from mine_config import MiningDRSConfig


def test_original_example_tracks_ore_stock_levels():
    import importlib

    original = importlib.import_module("example_mine_original")

    sim = original.ExampleMineModel(MiningDRSConfig())

    assert "OreStock_Level" in sim.telemetry.tracked_vars
    assert "Ore1Stock_Level" in sim.telemetry.tracked_vars
    assert "Ore2Stock_Level" in sim.telemetry.tracked_vars


def test_contingency_timer_resets_when_entering_mode_a_contingency():
    sim = ExampleMineModel(MiningDRSConfig())
    sim.controller.current_mode.value = MineMode.MODE_A
    sim.controller.time_executed_contingency.value = 0.75

    sim.check_transitions(sim.plant.ore2_stock, is_upper=False)

    assert sim.controller.current_mode.value == MineMode.MODE_A_CONTINGENCY
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_resets_when_entering_mode_b_contingency():
    sim = ExampleMineModel(MiningDRSConfig())
    sim.controller.current_mode.value = MineMode.MODE_B
    sim.controller.time_executed_contingency.value = 0.75

    sim.check_transitions(sim.plant.ore1_stock, is_upper=False)

    assert sim.controller.current_mode.value == MineMode.MODE_B_CONTINGENCY
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_does_not_reset_when_leaving_contingency():
    sim = ExampleMineModel(MiningDRSConfig())
    sim.controller.current_mode.value = MineMode.MODE_A_CONTINGENCY
    sim.controller.time_executed_contingency.value = 1.0

    sim.check_transitions(sim.controller.time_executed_contingency, is_upper=True)

    assert sim.controller.current_mode.value == MineMode.MODE_A
    assert sim.controller.time_executed_contingency.value == 1.0


def test_mine_surging_does_not_arm_component_ore_lower_bounds():
    sim = ExampleMineModel(MiningDRSConfig())

    sim.controller.current_mode.value = MineMode.MODE_A_MINE_SURGING
    sim.zero_rates()
    sim.update_rates()
    assert sim.plant.ore2_stock.lower_threshold == -math.inf

    sim.controller.current_mode.value = MineMode.MODE_B_MINE_SURGING
    sim.zero_rates()
    sim.update_rates()
    assert sim.plant.ore1_stock.lower_threshold == -math.inf
