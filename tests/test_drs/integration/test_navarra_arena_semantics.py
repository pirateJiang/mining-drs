import math
import sys
from pathlib import Path

NAVARRA_STANDARD = (
    Path(__file__).resolve().parents[3] / "examples" / "mining" / "standard"
)
if str(NAVARRA_STANDARD) not in sys.path:
    sys.path.insert(0, str(NAVARRA_STANDARD))

from examples.mining.components.modes import (
    ConcentratorModel,
    ModeA,
    ModeAContingency,
    ModeAMineSurging,
    ModeB,
    ModeBContingency,
    ModeBMineSurging,
    MiningDRSConfig,
)


def test_contingency_timer_resets_when_entering_mode_a_contingency():
    sim = ConcentratorModel(MiningDRSConfig())
    sim.controller.current_mode.value = ModeA()
    sim.controller.time_executed_contingency.value = 0.75
    sim.plant.ore2_stock.value = 0.0

    sim.check_transitions(sim.plant.ore2_stock, is_upper=False)

    assert isinstance(sim.controller.current_mode.value, ModeAContingency)
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_resets_when_entering_mode_b_contingency():
    sim = ConcentratorModel(MiningDRSConfig())
    sim.controller.current_mode.value = ModeB()
    sim.controller.time_executed_contingency.value = 0.75
    sim.plant.ore1_stock.value = 0.0

    sim.check_transitions(sim.plant.ore1_stock, is_upper=False)

    assert isinstance(sim.controller.current_mode.value, ModeBContingency)
    assert sim.controller.time_executed_contingency.value == 0.0


def test_contingency_timer_resets_when_leaving_contingency():
    sim = ConcentratorModel(MiningDRSConfig())
    sim.controller.current_mode.value = ModeAContingency()
    sim.controller.time_executed_contingency.upper_threshold = (
        sim.controller.config.duration_of_contingency_segments
    )
    sim.controller.time_executed_contingency.value = (
        sim.controller.config.duration_of_contingency_segments
    )

    sim.check_transitions(sim.controller.time_executed_contingency, is_upper=True)

    assert isinstance(sim.controller.current_mode.value, ModeA)
    assert sim.controller.time_executed_contingency.value == 0.0


def test_mine_surging_arms_component_ore_lower_bounds():
    sim = ConcentratorModel(MiningDRSConfig())

    sim.controller.current_mode.value = ModeAMineSurging()
    sim.update_rates()
    assert sim.plant.ore2_stock.lower_threshold == 0.0

    sim.controller.current_mode.value = ModeBMineSurging()
    sim.update_rates()
    assert sim.plant.ore1_stock.lower_threshold == 0.0
