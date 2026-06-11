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
from .modes import (
    ModeA,
    ModeAContingency,
    ModeAMineSurging,
    ModeB,
    ModeBContingency,
    ModeBMineSurging,
    Shutdown,
    ModeC,
    ModeCContingency,
    ModeCMineSurging,
    ModeD,
    ModeDContingency,
    ModeDMineSurging,
)


class BaseBlendingController(drs.Module):
    """
    Abstract base controller handling shared DRS timers and state transitions
    for dual-stockpile surging operations.
    """

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

        self.current_mode = drs.Variable("current_mode", ModeA())

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

        # All modes update campaign timer except shutdown, but shutdown updates it anyway
        # Actually let's just explicitly map what each mode updates.
        if m == "MODE_A":
            self.time_mode_a.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
        elif m == "MODE_A_CONTINGENCY":
            self.time_mode_a_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
            self.time_executed_contingency.upper_threshold = (
                c.duration_of_contingency_segments
            )
        elif m == "MODE_A_MINE_SURGING":
            self.time_mode_a_surging.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
        elif m == "MODE_B":
            self.time_mode_b.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
        elif m == "MODE_B_CONTINGENCY":
            self.time_mode_b_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
            self.time_executed_contingency.upper_threshold = (
                c.duration_of_contingency_segments
            )
        elif m == "MODE_B_MINE_SURGING":
            self.time_mode_b_surging.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
        elif m == "SHUTDOWN":
            self.time_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_shutdowns
            )

    def controller_decision(self):
        raise NotImplementedError(
            "Subclasses must implement the specific decision policy."
        )


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

    def controller_decision(self):
        c = self.config
        sensors = self.sensors
        m = self.current_mode.value.name

        ore1 = sensors.belief_ore1_stock.value
        ore2 = sensors.belief_ore2_stock.value
        total_stock = sensors.belief_ore_stock.value

        # 1. End of Campaign / Shutdown Check
        if self.is_campaign_complete():
            self.reset_campaign_timer()
            if m == "SHUTDOWN":
                # CSV Logic: If stock is already inflated, resume Surging immediately to burn it off
                if ore2 > c.critical_ore2_level:
                    return (
                        ModeA()
                        if total_stock <= c.target_ore_stock_level
                        else ModeAMineSurging()
                    )
                else:
                    return (
                        ModeB()
                        if total_stock <= c.target_ore_stock_level
                        else ModeBMineSurging()
                    )
            else:
                return Shutdown()

        # 2. End of Contingency Check
        if m in ("MODE_A_CONTINGENCY", "MODE_B_CONTINGENCY"):
            if self.is_contingency_complete():
                self.reset_contingency_timer()
                return ModeA() if m == "MODE_A_CONTINGENCY" else ModeB()

        # 3. Continuous Mid-Campaign Monitoring (Stockouts and Recoveries)
        if m == "MODE_A":
            if ore2 <= c.stockout_epsilon:
                return ModeAContingency()
            if ore1 <= c.stockout_epsilon:
                return ModeAMineSurging()

        elif m == "MODE_B":
            if ore1 <= c.stockout_epsilon:
                return ModeBContingency()
            if ore2 <= c.stockout_epsilon:
                return ModeBMineSurging()

        elif m == "MODE_A_CONTINGENCY":
            if ore1 <= c.stockout_epsilon:
                return ModeAMineSurging()

        elif m == "MODE_B_CONTINGENCY":
            if ore2 <= c.stockout_epsilon:
                return ModeBMineSurging()

        # 4. Exit Surging when the excess inventory is successfully burned off
        elif m == "MODE_A_MINE_SURGING":
            p = sensors.belief_routing_fraction
            is_good_parcel = (1.0 - p) > 0 and (
                c.mode_a_ore1_milling_rate / (1.0 - p)
            ) < (c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate)
            if total_stock <= c.target_ore_stock_level and is_good_parcel:
                return ModeA()

        elif m == "MODE_B_MINE_SURGING":
            p = sensors.belief_routing_fraction
            is_good_parcel = p > 0 and (c.mode_b_ore2_milling_rate / p) < (
                c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate
            )
            if total_stock <= c.target_ore_stock_level and is_good_parcel:
                return ModeB()

        return None


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

    def _update_timers(self, m: str):
        super()._update_timers(m)
        c = self.config
        if m == "MODE_C":
            self.time_mode_c.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
        elif m == "MODE_C_CONTINGENCY":
            self.time_mode_c_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
            self.time_executed_contingency.upper_threshold = (
                c.duration_of_contingency_segments
            )
        elif m == "MODE_C_MINE_SURGING":
            self.time_mode_c_surging.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
        elif m == "MODE_D":
            self.time_mode_d.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
        elif m == "MODE_D_CONTINGENCY":
            self.time_mode_d_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_contingency.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )
            self.time_executed_contingency.upper_threshold = (
                c.duration_of_contingency_segments
            )
        elif m == "MODE_D_MINE_SURGING":
            self.time_mode_d_surging.rate = 1.0
            self.time_executed_campaign_shutdown.rate = 1.0
            self.time_executed_campaign_shutdown.upper_threshold = (
                c.duration_of_production_campaigns
            )

    def controller_decision(self):
        c = self.config
        sensors = self.sensors
        m = self.current_mode.value.name

        ore1 = sensors.belief_ore1_stock.value
        ore2 = sensors.belief_ore2_stock.value
        total_stock = sensors.belief_ore_stock.value

        # The paper dictates that when production requirements increase (Period 27+),
        # the controller should evaluate switching to Configuration C or Configuration D.
        # Let's use the config variables directly to dynamically calculate period length.
        period_length = c.duration_of_production_campaigns + c.duration_of_shutdowns
        stage_2_start_time = c.stage_2_start_period * period_length
        is_stage_2 = self.parent.global_time.value >= stage_2_start_time

        # 1. End of Campaign / Shutdown Check
        if self.is_campaign_complete():
            self.reset_campaign_timer()
            if m == "SHUTDOWN":
                # In Stage 1, logic mimics the baseline Modes A and B
                if not is_stage_2:
                    if ore2 > c.critical_ore2_level:
                        return (
                            ModeA()
                            if total_stock <= c.target_ore_stock_level
                            else ModeAMineSurging()
                        )
                    else:
                        return (
                            ModeB()
                            if total_stock <= c.target_ore_stock_level
                            else ModeBMineSurging()
                        )
                # In Stage 2, it evaluates Mode C vs Mode D
                else:
                    if ore2 > c.critical_ore2_level:
                        return (
                            ModeC()
                            if total_stock <= c.target_ore_stock_level
                            else ModeCMineSurging()
                        )
                    else:
                        return (
                            ModeD()
                            if total_stock <= c.target_ore_stock_level
                            else ModeDMineSurging()
                        )
            else:
                return Shutdown()

        # 2. End of Contingency Check
        if m in (
            "MODE_A_CONTINGENCY",
            "MODE_B_CONTINGENCY",
            "MODE_C_CONTINGENCY",
            "MODE_D_CONTINGENCY",
        ):
            if self.is_contingency_complete():
                self.reset_contingency_timer()
                if m == "MODE_A_CONTINGENCY":
                    return ModeA()
                elif m == "MODE_B_CONTINGENCY":
                    return ModeB()
                elif m == "MODE_C_CONTINGENCY":
                    return ModeC()
                elif m == "MODE_D_CONTINGENCY":
                    return ModeD()

        # 3. Continuous Mid-Campaign Monitoring (Stockouts and Recoveries)
        if m == "MODE_A":
            if ore2 <= c.stockout_epsilon:
                return ModeAContingency()
            if ore1 <= c.stockout_epsilon:
                return ModeAMineSurging()
        elif m == "MODE_B":
            if ore1 <= c.stockout_epsilon:
                return ModeBContingency()
            if ore2 <= c.stockout_epsilon:
                return ModeBMineSurging()
        elif m == "MODE_C":
            if ore2 <= c.stockout_epsilon:
                return ModeCContingency()
            if ore1 <= c.stockout_epsilon:
                return ModeCMineSurging()
        elif m == "MODE_D":
            if ore1 <= c.stockout_epsilon:
                return ModeDContingency()
            if ore2 <= c.stockout_epsilon:
                return ModeDMineSurging()

        elif m == "MODE_A_CONTINGENCY":
            if ore1 <= c.stockout_epsilon:
                return ModeAMineSurging()
        elif m == "MODE_B_CONTINGENCY":
            if ore2 <= c.stockout_epsilon:
                return ModeBMineSurging()
        elif m == "MODE_C_CONTINGENCY":
            if ore1 <= c.stockout_epsilon:
                return ModeCMineSurging()
        elif m == "MODE_D_CONTINGENCY":
            if ore2 <= c.stockout_epsilon:
                return ModeDMineSurging()

        # 4. Exit Surging when the excess inventory is successfully burned off
        elif m == "MODE_A_MINE_SURGING":
            p = sensors.belief_routing_fraction
            is_good_parcel = (1.0 - p) > 0 and (
                c.mode_a_ore1_milling_rate / (1.0 - p)
            ) < (c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate)
            if total_stock <= c.target_ore_stock_level and is_good_parcel:
                return ModeA()

        elif m == "MODE_B_MINE_SURGING":
            p = sensors.belief_routing_fraction
            is_good_parcel = p > 0 and (c.mode_b_ore2_milling_rate / p) < (
                c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate
            )
            if total_stock <= c.target_ore_stock_level and is_good_parcel:
                return ModeB()

        elif m == "MODE_C_MINE_SURGING":
            p = sensors.belief_routing_fraction
            is_good_parcel = (1.0 - p) > 0 and (
                c.mode_c_ore1_milling_rate / (1.0 - p)
            ) < (c.mode_c_ore1_milling_rate + c.mode_c_ore2_milling_rate)
            if total_stock <= c.target_ore_stock_level and is_good_parcel:
                return ModeC()

        elif m == "MODE_D_MINE_SURGING":
            p = sensors.belief_routing_fraction
            is_good_parcel = p > 0 and (c.mode_d_ore2_milling_rate / p) < (
                c.mode_d_ore1_milling_rate + c.mode_d_ore2_milling_rate
            )
            if total_stock <= c.target_ore_stock_level and is_good_parcel:
                return ModeD()

        return None
