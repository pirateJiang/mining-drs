from drs.module import drs
from drs.flow import Flow
from .modes import OperatingMode, RequireDecision
from .config import ConcentratorConfig
from .supply_chain import (
    BaseMineFace,
    BaseFleetLogistics,
    BaseMetallurgicalPlant,
    ConcentratorMineFace,
    ConcentratorFleet,
    ConcentratorPlant,
)
from .modes import MODES


class BaseBlendingController(drs.Module):
    _TIMER_MAP = {
        "MODE_A": "cumulative_time_mode_a",
        "MODE_A_CONTINGENCY": "cumulative_time_mode_a_contingency",
        "MODE_A_MINE_SURGING": "cumulative_time_mode_a_surging",
        "MODE_B": "cumulative_time_mode_b",
        "MODE_B_CONTINGENCY": "cumulative_time_mode_b_contingency",
        "MODE_B_MINE_SURGING": "cumulative_time_mode_b_surging",
        "SHUTDOWN": "cumulative_time_shutdown",
    }
    _CONTINGENCY_MODES = {"MODE_A_CONTINGENCY", "MODE_B_CONTINGENCY"}

    def __init__(
        self,
        config,
        mine: BaseMineFace,
        fleet: BaseFleetLogistics,
        plant: BaseMetallurgicalPlant,
    ):
        super().__init__()
        self.config = config
        self.mine = mine
        self.fleet = fleet
        self.plant = plant

        self.active_operating_mode = drs.Variable("active_operating_mode", MODES["MODE_A"])
        self.total_system_ore_mass = drs.Level("total_system_ore_mass", initial_value=config.target_ore_stock_level)

        self.current_campaign_duration = drs.Timer(
            "current_campaign_duration", initial_value=0.0
        )
        self.current_contingency_duration = drs.Timer(
            "current_contingency_duration", initial_value=0.0
        )
        self.cumulative_time_mode_a = drs.Timer("cumulative_time_mode_a", initial_value=0.0)
        self.cumulative_time_mode_a_contingency = drs.Timer(
            "cumulative_time_mode_a_contingency", initial_value=0.0
        )
        self.cumulative_time_mode_a_surging = drs.Timer(
            "cumulative_time_mode_a_surging", initial_value=0.0
        )
        self.cumulative_time_mode_b = drs.Timer("cumulative_time_mode_b", initial_value=0.0)
        self.cumulative_time_mode_b_contingency = drs.Timer(
            "cumulative_time_mode_b_contingency", initial_value=0.0
        )
        self.cumulative_time_mode_b_surging = drs.Timer(
            "cumulative_time_mode_b_surging", initial_value=0.0
        )
        self.cumulative_time_shutdown = drs.Timer("cumulative_time_shutdown", initial_value=0.0)

        self.target_mine_mass_rate = drs.Variable("target_mine_mass_rate", 0.0)
        self.target_stock1_outflow_rate = drs.Variable("target_stock1_outflow_rate", 0.0)
        self.target_stock2_outflow_rate = drs.Variable("target_stock2_outflow_rate", 0.0)

    def is_campaign_complete(self) -> bool:
        c = self.config
        m = self.active_operating_mode.value.name
        threshold = (
            c.duration_of_shutdowns
            if m == "SHUTDOWN"
            else c.duration_of_production_campaigns
        )

        self.current_campaign_duration.upper_threshold = threshold

        return self.current_campaign_duration.value >= (threshold - 1e-6)

    def is_contingency_complete(self) -> bool:
        c = self.config
        threshold = c.duration_of_contingency_segments

        self.current_contingency_duration.upper_threshold = threshold

        return self.current_contingency_duration.value >= (threshold - 1e-6)

    def reset_campaign_timer(self):
        self.current_campaign_duration.reset()

    def reset_contingency_timer(self):
        self.current_contingency_duration.reset()

    def forward(self) -> Flow:
        c = self.config
        mine = self.mine

        if (
            abs(
                mine.cumulative_extracted_mass.value
                - c.ore_to_be_extracted_during_warming_period
            )
            < 1e-6
        ):
            self.cumulative_time_mode_a.reset()
            self.cumulative_time_mode_a_contingency.reset()
            self.cumulative_time_mode_a_surging.reset()
            self.cumulative_time_mode_b.reset()
            self.cumulative_time_mode_b_contingency.reset()
            self.cumulative_time_mode_b_surging.reset()
            self.cumulative_time_shutdown.reset()

        extraction_rate = self.mine.cumulative_extracted_mass.rate
        milled_rate = self.plant.cumulative_milled_mass.rate
        self.total_system_ore_mass.rate = extraction_rate - milled_rate

        next_mode = self.active_operating_mode.value.check_end_conditions(self.parent)

        if isinstance(next_mode, RequireDecision):
            decision = self.controller_decision()
            if decision:
                next_mode = decision

        if next_mode:
            self.active_operating_mode.value = next_mode

        self._update_timers(self.active_operating_mode.value.name)

        targets = self.active_operating_mode.value.get_target_rates(self.parent)
        self.target_mine_mass_rate.value = targets.extraction_rate
        self.target_stock1_outflow_rate.value = targets.ore1_milling_rate
        self.target_stock2_outflow_rate.value = targets.ore2_milling_rate

    def _update_timers(self, m: str):
        c = self.config
        timer_attr = self._TIMER_MAP.get(m)
        if timer_attr:
            getattr(self, timer_attr).rate = 1.0
        self.current_campaign_duration.rate = 1.0
        self.current_campaign_duration.upper_threshold = (
            c.duration_of_shutdowns if m == "SHUTDOWN" else c.duration_of_production_campaigns
        )
        if m in self._CONTINGENCY_MODES:
            self.current_contingency_duration.rate = 1.0
            self.current_contingency_duration.upper_threshold = c.duration_of_contingency_segments

    def _choose_next_campaign_mode(self, config):
        ore2 = self.parent.ore2_stock.current_mass.value
        total_stock = self.total_system_ore_mass.value
        if ore2 > config.critical_ore2_level:
            return (
                MODES["MODE_A"]
                if total_stock <= config.target_ore_stock_level
                else MODES["MODE_A_MINE_SURGING"]
            )
        else:
            return (
                MODES["MODE_B"]
                if total_stock <= config.target_ore_stock_level
                else MODES["MODE_B_MINE_SURGING"]
            )

    def controller_decision(self):
        c = self.config
        m = self.active_operating_mode.value.name

        if self.is_campaign_complete():
            self.reset_campaign_timer()
            if m == "SHUTDOWN":
                return self._choose_next_campaign_mode(c)
            return MODES["SHUTDOWN"]

        if m.endswith("_CONTINGENCY"):
            self.reset_contingency_timer()
        base = m.replace("_CONTINGENCY", "").replace("_MINE_SURGING", "")
        return MODES[base]


class ConcentratorController(BaseBlendingController):
    def __init__(
        self,
        config: ConcentratorConfig,
        mine: ConcentratorMineFace,
        fleet: ConcentratorFleet,
        plant: ConcentratorPlant,
    ):
        super().__init__(config, mine, fleet, plant)



