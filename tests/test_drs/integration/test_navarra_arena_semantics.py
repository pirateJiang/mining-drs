import math
import sys
from pathlib import Path

NAVARRA_STANDARD = (
    Path(__file__).resolve().parents[3] / "examples" / "mining" / "standard"
)
if str(NAVARRA_STANDARD) not in sys.path:
    sys.path.insert(0, str(NAVARRA_STANDARD))

from examples.mining.components.modes import (
    ModeA,
    ModeAContingency,
    ModeAMineSurging,
    ModeB,
    ModeBContingency,
    ModeBMineSurging,
)
from examples.mining.components.models import ConcentratorModel
from examples.mining.components.config import ConcentratorConfig


def test_contingency_timer_resets_when_entering_mode_a_contingency():
    sim = ConcentratorModel(ConcentratorConfig())
    sim.controller.current_mode.value = ModeA()
    sim.controller.time_executed_contingency.value = 0.75
    # Force Ore 2 stockout to trigger contingency
    sim.sensors.belief_ore2_stock.value = 0.0

    result = sim.controller.forward()

    assert isinstance(result, ModeAContingency)
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_resets_when_entering_mode_b_contingency():
    sim = ConcentratorModel(ConcentratorConfig())
    sim.controller.current_mode.value = ModeB()
    sim.controller.time_executed_contingency.value = 0.75
    # Force Ore 1 stockout to trigger contingency
    sim.sensors.belief_ore1_stock.value = 0.0

    result = sim.controller.forward()

    assert isinstance(result, ModeBContingency)
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_resets_when_leaving_contingency():
    sim = ConcentratorModel(ConcentratorConfig())
    sim.controller.current_mode.value = ModeAContingency()
    sim.controller.time_executed_contingency.value = (
        sim.controller.config.duration_of_contingency_segments
    )
    # Campaign timer is managed by is_campaign_complete - set it below threshold
    sim.controller.time_executed_campaign_shutdown.value = 0.0

    result = sim.controller.forward()

    assert isinstance(result, ModeA)
    assert sim.controller.time_executed_contingency.value == 0.0


def test_mine_surging_arms_component_ore_lower_bounds():
    sim = ConcentratorModel(ConcentratorConfig())

    # Simulate excess stock so surging mode doesn't immediately exit
    sim.sensors.belief_ore_stock.value = sim.config.target_ore_stock_level * 1.1

    # Mode A Mine Surging sets belief_ore_stock lower_threshold to trigger
    # exit when excess inventory is burned back down to the target level
    sim.controller.current_mode.value = ModeAMineSurging()
    sim.controller.forward()

    assert sim.sensors.belief_ore_stock.lower_threshold == sim.config.target_ore_stock_level

    sim.controller.current_mode.value = ModeBMineSurging()
    sim.controller.forward()

    assert sim.sensors.belief_ore_stock.lower_threshold == sim.config.target_ore_stock_level
