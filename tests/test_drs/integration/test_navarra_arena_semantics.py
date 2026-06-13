import math
import sys
from pathlib import Path

NAVARRA_STANDARD = (
    Path(__file__).resolve().parents[3] / "examples" / "mining" / "standard"
)
if str(NAVARRA_STANDARD) not in sys.path:
    sys.path.insert(0, str(NAVARRA_STANDARD))

from examples.mining.components.modes import MODES
from examples.mining.components.models import ConcentratorModel
from examples.mining.components.config import ConcentratorConfig


def test_contingency_timer_resets_when_entering_mode_a_contingency():
    sim = ConcentratorModel(ConcentratorConfig())
    sim.ore2_stock.current_mass.value = 0.0
    sim.controller.current_mode.value = MODES["MODE_A"]
    sim.controller.time_executed_contingency.value = 0.75

    result = sim.controller.forward()

    assert result is MODES["MODE_A_CONTINGENCY"]
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_resets_when_entering_mode_b_contingency():
    sim = ConcentratorModel(ConcentratorConfig())
    sim.ore1_stock.current_mass.value = 0.0
    sim.controller.current_mode.value = MODES["MODE_B"]
    sim.controller.time_executed_contingency.value = 0.75

    result = sim.controller.forward()

    assert result is MODES["MODE_B_CONTINGENCY"]
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_resets_when_leaving_contingency():
    sim = ConcentratorModel(ConcentratorConfig())
    sim.controller.current_mode.value = MODES["MODE_A_CONTINGENCY"]
    sim.controller.time_executed_contingency.value = (
        sim.controller.config.duration_of_contingency_segments
    )
    sim.controller.time_executed_campaign_shutdown.value = 0.0

    result = sim.controller.forward()

    assert result is MODES["MODE_A"]
    assert sim.controller.time_executed_contingency.value == 0.0


def test_mine_surging_arms_component_ore_lower_bounds():
    sim = ConcentratorModel(ConcentratorConfig())

    sim.plant.true_ore_stock.value = sim.config.target_ore_stock_level * 1.1

    sim.controller.current_mode.value = MODES["MODE_A_MINE_SURGING"]
    sim.controller.forward()

    assert sim.plant.true_ore_stock.lower_threshold == sim.config.target_ore_stock_level

    sim.controller.current_mode.value = MODES["MODE_B_MINE_SURGING"]
    sim.controller.forward()

    assert sim.plant.true_ore_stock.lower_threshold == sim.config.target_ore_stock_level
