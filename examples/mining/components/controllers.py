from drs.module import drs
from .modes import OperatingMode, RequireDecision
from .sensors import (
    BaseSensorNetwork,
    ConcentratorSensorNetwork,
    CyanidationSensorNetwork,
)
from .config import ConcentratorConfig, CyanidationConfig
from .supply_chain import (
    BaseMineFace,
    BaseFleetLogistics,
    BaseMetallurgicalPlant,
    ConcentratorMineFace,
    ConcentratorFleet,
    ConcentratorPlant,
    CyanidationMineFace,
    CyanidationFleet,
    CyanidationPlant,
)
from .modes import MODES


class BaseBlendingController(drs.Module):
    """
    Abstract base controller handling shared DRS timers and state transitions
    for dual-stockpile surging operations.
    """

    _TIMER_MAP = {
        "MODE_A": "time_mode_a",
        "MODE_A_CONTINGENCY": "time_mode_a_contingency",
        "MODE_A_MINE_SURGING": "time_mode_a_surging",
        "MODE_B": "time_mode_b",
        "MODE_B_CONTINGENCY": "time_mode_b_contingency",
        "MODE_B_MINE_SURGING": "time_mode_b_surging",
        "SHUTDOWN": "time_shutdown",
    }
    _CONTINGENCY_MODES = {"MODE_A_CONTINGENCY", "MODE_B_CONTINGENCY"}

    def __init__(
        self,
        config,
        sensors: BaseSensorNetwork,
        mine: BaseMineFace,
        fleet: BaseFleetLogistics,
        plant: BaseMetallurgicalPlant,
    ):
        super().__init__()
        self.config = config
        self.sensors = sensors
        self.mine = mine
        self.fleet = fleet
        self.plant = plant

        self.current_mode = drs.Variable("current_mode", MODES["MODE_A"])

        # Initial Timer Values
        self.time_executed_campaign_shutdown = drs.Timer(
            "TimeExecutedInCurrentCampaignOrShutdown_Timer", initial_value=0.0
        )
        self.time_executed_contingency = drs.Timer(
            "TimeExecutedInCurrentContingencySegment_Timer", initial_value=0.0
        )
        self.time_mode_a = drs.Timer("TimeInModeA_Timer", initial_value=0.0)
        self.time_mode_a_contingency = drs.Timer(
            "TimeInModeAContingency_Timer", initial_value=0.0
        )
        self.time_mode_a_surging = drs.Timer(
            "TimeInModeAMineSurging_Timer", initial_value=0.0
        )
        self.time_mode_b = drs.Timer("TimeInModeB_Timer", initial_value=0.0)
        self.time_mode_b_contingency = drs.Timer(
            "TimeInModeBContingency_Timer", initial_value=0.0
        )
        self.time_mode_b_surging = drs.Timer(
            "TimeInModeBMineSurging_Timer", initial_value=0.0
        )
        self.time_shutdown = drs.Timer("TimeInShutdown_Level", initial_value=0.0)

    def is_campaign_complete(self) -> bool:
        c = self.config
        m = self.current_mode.value.name
        threshold = (
            c.duration_of_shutdowns
            if m == "SHUTDOWN"
            else c.duration_of_production_campaigns
        )

        # CRITICAL FIX: Tell the engine exactly when to stop time!
        self.time_executed_campaign_shutdown.upper_threshold = threshold

        return self.time_executed_campaign_shutdown.value >= (threshold - 1e-6)

    def is_contingency_complete(self) -> bool:
        c = self.config
        threshold = c.duration_of_contingency_segments

        # CRITICAL FIX: Tell the engine exactly when to stop time!
        self.time_executed_contingency.upper_threshold = threshold

        return self.time_executed_contingency.value >= (threshold - 1e-6)

    def reset_campaign_timer(self):
        self.time_executed_campaign_shutdown.reset()

    def reset_contingency_timer(self):
        self.time_executed_contingency.reset()

    def forward(self) -> OperatingMode:
        # Silently read the sensor to draw the computational graph edge
        _ = self.sensors.belief_ore_stock.value

        c = self.config
        mine = self.mine

        # Global warmup reset
        if (
            abs(
                mine.true_ore_extraction.value
                - c.ore_to_be_extracted_during_warming_period
            )
            < 1e-6
        ):
            self.time_mode_a.reset()
            self.time_mode_a_contingency.reset()
            self.time_mode_a_surging.reset()
            self.time_mode_b.reset()
            self.time_mode_b_contingency.reset()
            self.time_mode_b_surging.reset()
            self.time_shutdown.reset()

        # Mode-specific transitions
        next_mode = self.current_mode.value.check_end_conditions(self.parent)

        if isinstance(next_mode, RequireDecision):
            decision = self.controller_decision()
            if decision:
                next_mode = decision

        if next_mode:
            self.current_mode.value = next_mode

        self._update_timers(self.current_mode.value.name)

        return self.current_mode.value

    def _update_timers(self, m: str):
        c = self.config
        timer_attr = self._TIMER_MAP.get(m)
        if timer_attr:
            getattr(self, timer_attr).rate = 1.0
        self.time_executed_campaign_shutdown.rate = 1.0
        self.time_executed_campaign_shutdown.upper_threshold = (
            c.duration_of_shutdowns if m == "SHUTDOWN" else c.duration_of_production_campaigns
        )
        if m in self._CONTINGENCY_MODES:
            self.time_executed_contingency.rate = 1.0
            self.time_executed_contingency.upper_threshold = c.duration_of_contingency_segments

    def _choose_next_campaign_mode(self, sensors, config):
        ore2 = sensors.belief_ore2_stock.value
        total_stock = sensors.belief_ore_stock.value
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
        sensors = self.sensors
        m = self.current_mode.value.name

        if self.is_campaign_complete():
            self.reset_campaign_timer()
            if m == "SHUTDOWN":
                return self._choose_next_campaign_mode(sensors, c)
            return MODES["SHUTDOWN"]

        if m.endswith("_CONTINGENCY"):
            self.reset_contingency_timer()
        base = m.replace("_CONTINGENCY", "").replace("_MINE_SURGING", "")
        return MODES[base]


class ConcentratorController(BaseBlendingController):
    """
    Standard decision logic for the Base-Metal Concentrator.
    Loops infinitely between Modes A and B based on critical Ore 2 levels.
    """

    def __init__(
        self,
        config: ConcentratorConfig,
        sensors: ConcentratorSensorNetwork,
        mine: ConcentratorMineFace,
        fleet: ConcentratorFleet,
        plant: ConcentratorPlant,
    ):
        super().__init__(config, sensors, mine, fleet, plant)


class CyanidationController(BaseBlendingController):
    """
    Decision logic for the Au-Ag Cyanidation Plant.
    Currently identical to Concentrator logic, but structured to support
    the transition to Stage 2 (Modes C & D) halfway through the mine life.
    """

    def __init__(
        self,
        config: CyanidationConfig,
        sensors: CyanidationSensorNetwork,
        mine: CyanidationMineFace,
        fleet: CyanidationFleet,
        plant: CyanidationPlant,
    ):
        super().__init__(config, sensors, mine, fleet, plant)

        # Stage 2 Timers (Specific to Cyanidation)
        self.time_mode_c = drs.Timer("TimeInModeC_Timer", initial_value=0.0)
        self.time_mode_c_contingency = drs.Timer(
            "TimeInModeCContingency_Timer", initial_value=0.0
        )
        self.time_mode_c_surging = drs.Timer(
            "TimeInModeCMineSurging_Timer", initial_value=0.0
        )
        self.time_mode_d = drs.Timer("TimeInModeD_Timer", initial_value=0.0)
        self.time_mode_d_contingency = drs.Timer(
            "TimeInModeDContingency_Timer", initial_value=0.0
        )
        self.time_mode_d_surging = drs.Timer(
            "TimeInModeDMineSurging_Timer", initial_value=0.0
        )

    _TIMER_MAP = {
        **BaseBlendingController._TIMER_MAP,
        "MODE_C": "time_mode_c",
        "MODE_C_CONTINGENCY": "time_mode_c_contingency",
        "MODE_C_MINE_SURGING": "time_mode_c_surging",
        "MODE_D": "time_mode_d",
        "MODE_D_CONTINGENCY": "time_mode_d_contingency",
        "MODE_D_MINE_SURGING": "time_mode_d_surging",
    }
    _CONTINGENCY_MODES = BaseBlendingController._CONTINGENCY_MODES | {
        "MODE_C_CONTINGENCY", "MODE_D_CONTINGENCY",
    }

    def forward(self) -> OperatingMode:
        c = self.config
        mine = self.mine

        if (
            abs(
                mine.true_ore_extraction.value
                - c.ore_to_be_extracted_during_warming_period
            )
            < 1e-6
        ):
            self.time_mode_c.reset()
            self.time_mode_c_contingency.reset()
            self.time_mode_c_surging.reset()
            self.time_mode_d.reset()
            self.time_mode_d_contingency.reset()
            self.time_mode_d_surging.reset()

        return super().forward()

    def _choose_next_campaign_mode(self, sensors, config):
        ore2 = sensors.belief_ore2_stock.value
        total_stock = sensors.belief_ore_stock.value
        period_length = config.duration_of_production_campaigns + config.duration_of_shutdowns
        stage_2_start_time = config.stage_2_start_period * period_length
        is_stage_2 = self.parent.global_time.value >= stage_2_start_time

        if not is_stage_2:
            return super()._choose_next_campaign_mode(sensors, config)
        if ore2 > config.critical_ore2_level:
            return (
                MODES["MODE_C"]
                if total_stock <= config.target_ore_stock_level
                else MODES["MODE_C_MINE_SURGING"]
            )
        else:
            return (
                MODES["MODE_D"]
                if total_stock <= config.target_ore_stock_level
                else MODES["MODE_D_MINE_SURGING"]
            )
