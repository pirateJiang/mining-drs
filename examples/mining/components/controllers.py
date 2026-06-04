from drs.module import drs
from drs.modes import RequireDecision
from .config import ConcentratorConfig, CyanidationConfig
from .plants import ConcentratorPlant, CyanidationPlant
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

    def __init__(self, config, plant):
        super().__init__()
        self.config = config
        self.plant = plant

        self.current_mode = drs.State("current_mode", ModeA())

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
        return (
            self.time_executed_campaign_shutdown.value
            >= self.time_executed_campaign_shutdown.upper_threshold
        )

    def is_contingency_complete(self) -> bool:
        return (
            self.time_executed_contingency.value
            >= self.time_executed_contingency.upper_threshold
        )

    def reset_campaign_timer(self):
        self.time_executed_campaign_shutdown.reset()

    def reset_contingency_timer(self):
        self.time_executed_contingency.reset()

    def update_rates(self):
        self.current_mode.value.apply_dynamics(self.parent)

    def check_transitions(
        self, trigger_var: drs.Variable = None, is_upper: bool = True
    ):
        c = self.config
        plant = self.plant

        # Global warmup reset
        if trigger_var == plant.ore_extraction and is_upper:
            if (
                abs(
                    plant.ore_extraction.value
                    - c.ore_to_be_extracted_during_warming_period
                )
                < 0.1
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

    def controller_decision(self):
        raise NotImplementedError(
            "Subclasses must implement the specific decision policy."
        )


class ConcentratorController(BaseBlendingController):
    """
    Standard decision logic for the Base-Metal Concentrator.
    Loops infinitely between Modes A and B based on critical Ore 2 levels.
    """

    def __init__(self, config: ConcentratorConfig, plant: ConcentratorPlant):
        super().__init__(config, plant)

    def controller_decision(self):
        c = self.config
        plant = self.plant
        m = self.current_mode.value.name

        if self.is_campaign_complete():
            self.reset_campaign_timer()
            if m == "SHUTDOWN":
                if plant.ore2_stock.value > c.critical_ore2_level:
                    return (
                        ModeA()
                        if plant.ore_stock.value <= c.target_ore_stock_level
                        else ModeAMineSurging()
                    )
                else:
                    return (
                        ModeB()
                        if plant.ore_stock.value <= c.target_ore_stock_level
                        else ModeBMineSurging()
                    )
            else:
                return Shutdown()

        if m in ("MODE_A_CONTINGENCY", "MODE_B_CONTINGENCY"):
            if self.is_contingency_complete():
                self.reset_contingency_timer()
                return ModeA() if m == "MODE_A_CONTINGENCY" else ModeB()

        if m in ("MODE_A_MINE_SURGING", "MODE_B_MINE_SURGING"):
            if plant.ore_stock.value <= c.target_ore_stock_level:
                return ModeA() if m == "MODE_A_MINE_SURGING" else ModeB()

        return None


class CyanidationController(BaseBlendingController):
    """
    Decision logic for the Au-Ag Cyanidation Plant.
    Currently identical to Concentrator logic, but structured to support
    the transition to Stage 2 (Modes C & D) halfway through the mine life.
    """

    def __init__(self, config: CyanidationConfig, plant: CyanidationPlant):
        super().__init__(config, plant)
        
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

    def check_transitions(self, trigger_var: drs.Variable = None, is_upper: bool = True):
        # Let base class handle standard transitions and base timer resets
        super().check_transitions(trigger_var, is_upper)
        
        # Also handle specific warmup reset for Stage 2 timers
        c = self.config
        plant = self.plant
        if trigger_var == plant.ore_extraction and is_upper:
            if (
                abs(plant.ore_extraction.value - c.ore_to_be_extracted_during_warming_period) < 0.1
            ):
                self.time_mode_c.reset()
                self.time_mode_c_contingency.reset()
                self.time_mode_c_surging.reset()
                self.time_mode_d.reset()
                self.time_mode_d_contingency.reset()
                self.time_mode_d_surging.reset()

    def controller_decision(self):
        c = self.config
        plant = self.plant
        m = self.current_mode.value.name

        # The paper dictates that when production requirements increase (Period 27+),
        # the controller should evaluate switching to Configuration C or Configuration D.
        # A single period is a 34-day production campaign + 1-day shutdown? Wait, user said 29-day campaign + 1-day shutdown = 30 days.
        # Let's use the config variables directly to dynamically calculate period length.
        period_length = c.duration_of_production_campaigns + c.duration_of_shutdowns
        stage_2_start_time = c.stage_2_start_period * period_length
        is_stage_2 = self.parent.global_time.value >= stage_2_start_time

        if self.is_campaign_complete():
            self.reset_campaign_timer()
            if m == "SHUTDOWN":

                # In Stage 1, logic mimics the baseline Modes A and B
                if not is_stage_2:
                    if plant.ore2_stock.value > c.critical_ore2_level:
                        return (
                            ModeA()
                            if plant.ore_stock.value <= c.target_ore_stock_level
                            else ModeAMineSurging()
                        )
                    else:
                        return (
                            ModeB()
                            if plant.ore_stock.value <= c.target_ore_stock_level
                            else ModeBMineSurging()
                        )

                # In Stage 2, it evaluates Mode C vs Mode D
                else:
                    if plant.ore2_stock.value > c.critical_ore2_level:
                        return (
                            ModeC()
                            if plant.ore_stock.value <= c.target_ore_stock_level
                            else ModeCMineSurging()
                        )
                    else:
                        return (
                            ModeD()
                            if plant.ore_stock.value <= c.target_ore_stock_level
                            else ModeDMineSurging()
                        )

            else:
                return Shutdown()

        if m in ("MODE_A_CONTINGENCY", "MODE_B_CONTINGENCY", "MODE_C_CONTINGENCY", "MODE_D_CONTINGENCY"):
            if self.is_contingency_complete():
                self.reset_contingency_timer()
                if m == "MODE_A_CONTINGENCY": return ModeA()
                elif m == "MODE_B_CONTINGENCY": return ModeB()
                elif m == "MODE_C_CONTINGENCY": return ModeC()
                elif m == "MODE_D_CONTINGENCY": return ModeD()

        if m in ("MODE_A_MINE_SURGING", "MODE_B_MINE_SURGING", "MODE_C_MINE_SURGING", "MODE_D_MINE_SURGING"):
            if plant.ore_stock.value <= c.target_ore_stock_level:
                if m == "MODE_A_MINE_SURGING": return ModeA()
                elif m == "MODE_B_MINE_SURGING": return ModeB()
                elif m == "MODE_C_MINE_SURGING": return ModeC()
                elif m == "MODE_D_MINE_SURGING": return ModeD()

        return None
