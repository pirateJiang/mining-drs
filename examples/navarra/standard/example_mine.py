import math
import random
from enum import Enum
from mining_drs import drs, DRSEngine
from mine_config import MiningDRSConfig
from mining_drs.telemetry import Telemetry
from mining_drs.modes import StateMachine


# The MineMode enum defines the discrete, mutually exclusive operational states of the mining plant.
# - MODE_A / MODE_B: Standard production modes representing different ore blending and extraction strategies.
# - CONTINGENCY modes (A/B): Fallback states activated when a specific ore type (Ore 1 or Ore 2) is completely depleted.
# - SURGING modes (A/B): High-throughput states triggered when the total ore stock drops dangerously low, aiming to quickly replenish it.
# - SHUTDOWN: Planned non-productive periods representing maintenance or downtime between active production campaigns.

# Mode A (Normal Operation): This is the primary, default operating state. The plant stays in Mode A logic as long as the stock of Ore 2 remains healthy (i.e., above the critical_ore2_level). In this mode, the plant processes Ore 1 and Ore 2 at its standard, preferred milling rates (mode_a_ore1_milling_rate and mode_a_ore2_milling_rate).
# Mode B (Ore 2 Conservation/Recovery): The plant shifts to Mode B logic when the Ore 2 stock drops to a critically low level (below critical_ore2_level). When this happens, the plant changes its extraction and milling strategy to mode_b rates. This alternate strategy typically adjusts the blending ratio to put less strain on the dwindling Ore 2 stockpile, giving the mine a chance to extract and replenish it.


class MineMode(Enum):
    MODE_A = "ModeA"
    MODE_A_CONTINGENCY = "ModeAContingency"
    MODE_A_MINE_SURGING = "ModeAMineSurging"
    MODE_B = "ModeB"
    MODE_B_CONTINGENCY = "ModeBContingency"
    MODE_B_MINE_SURGING = "ModeBMineSurging"
    SHUTDOWN = "Shutdown"


class MinePlant(drs.Module):
    def __init__(self, config: MiningDRSConfig):
        super().__init__()
        self.config = config

        # Parcel State
        self.mass_of_current_parcel = 40000.0
        self.percentage_of_ore2 = self.config.mean_grade_new_facies
        self.next_parcel_is_new_facies = True

        # Initial Level Values
        self.ore_extraction = drs.Level("OreExtraction_Level", initial_value=0.0)
        self.ore_extracted_from_current_parcel = drs.Level(
            "OreExtractedFromCurrentParcel_Level", initial_value=0.0
        )
        self.ore_stock = drs.Level(
            "OreStock_Level", initial_value=self.config.target_ore_stock_level
        )
        self.ore1_stock = drs.Level(
            "Ore1Stock_Level",
            initial_value=(1 - (self.config.mean_grade_new_facies / 100.0))
            * self.config.target_ore_stock_level,
        )
        self.ore2_stock = drs.Level(
            "Ore2Stock_Level",
            initial_value=(self.config.mean_grade_new_facies / 100.0)
            * self.config.target_ore_stock_level,
        )

    def _generate_next_parcel(self):
        c = self.config
        self.ore_extracted_from_current_parcel.value = 0.0
        self.mass_of_current_parcel = random.uniform(c.min_ore_mass, c.max_ore_mass)

        if self.next_parcel_is_new_facies:
            if c.std_dev_new_facies != 0:
                val = random.gauss(c.mean_grade_new_facies, c.std_dev_new_facies)
            else:
                val = c.mean_grade_new_facies
            self.percentage_of_ore2 = max(val, 0.0)
        else:
            val = self.percentage_of_ore2 + c.variation_same_facies * random.uniform(
                -1, 1
            )
            self.percentage_of_ore2 = max(val, 0.0)

        self.next_parcel_is_new_facies = random.random() <= c.prob_new_facies

    def update_rates(self, mode: MineMode):
        c = self.config
        # Apply Global / Shared Rules for plant
        if (
            self.ore_extraction.value
            < self.config.ore_to_be_extracted_during_warming_period
        ):
            self.ore_extraction.upper_threshold = (
                self.config.ore_to_be_extracted_during_warming_period
            )
        else:
            self.ore_extraction.upper_threshold = self.config.total_ore_to_extract

        self.ore_extracted_from_current_parcel.upper_threshold = (
            self.mass_of_current_parcel
        )

        p = self.percentage_of_ore2

        # Apply mode-specific rates
        if mode == MineMode.MODE_A:
            r = c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate
            self.ore_extraction.rate = r
            self.ore_extracted_from_current_parcel.rate = r
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = r * (1 - p / 100) - c.mode_a_ore1_milling_rate
            self.ore2_stock.rate = r * (p / 100) - c.mode_a_ore2_milling_rate
            self.ore1_stock.lower_threshold = 0.0
            self.ore2_stock.lower_threshold = 0.0
        elif mode == MineMode.MODE_A_CONTINGENCY:
            r = c.mode_a_contingency_ore1_milling_rate
            self.ore_extraction.rate = r
            self.ore_extracted_from_current_parcel.rate = r
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = r * (1 - p / 100) - r
            self.ore2_stock.rate = r * (p / 100)
            self.ore1_stock.lower_threshold = 0.0
        elif mode == MineMode.MODE_A_MINE_SURGING:
            r = c.mode_a_ore1_milling_rate * 100 / (100 - p)
            self.ore_extraction.rate = r
            self.ore_extracted_from_current_parcel.rate = r
            self.ore_stock.rate = (
                r - c.mode_a_ore1_milling_rate - c.mode_a_ore2_milling_rate
            )
            self.ore1_stock.rate = 0.0
            self.ore2_stock.rate = r * (p / 100) - c.mode_a_ore2_milling_rate
            self.ore_stock.lower_threshold = c.target_ore_stock_level
            self.ore2_stock.lower_threshold = 0.0
        elif mode == MineMode.MODE_B:
            r = c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate
            self.ore_extraction.rate = r
            self.ore_extracted_from_current_parcel.rate = r
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = r * (100 - p) / 100 - c.mode_b_ore1_milling_rate
            self.ore2_stock.rate = r * (p / 100) - c.mode_b_ore2_milling_rate
            self.ore1_stock.lower_threshold = 0.0
            self.ore2_stock.lower_threshold = 0.0
        elif mode == MineMode.MODE_B_CONTINGENCY:
            r = c.mode_b_contingency_ore2_milling_rate
            self.ore_extraction.rate = r
            self.ore_extracted_from_current_parcel.rate = r
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = r * (100 - p) / 100
            self.ore2_stock.rate = r * (p / 100) - r
            self.ore2_stock.lower_threshold = 0.0
        elif mode == MineMode.MODE_B_MINE_SURGING:
            r = c.mode_b_ore2_milling_rate * 100 / p
            self.ore_extraction.rate = r
            self.ore_extracted_from_current_parcel.rate = r
            self.ore_stock.rate = (
                r - c.mode_b_ore1_milling_rate - c.mode_b_ore2_milling_rate
            )
            self.ore1_stock.rate = r * (100 - p) / 100 - c.mode_b_ore1_milling_rate
            self.ore2_stock.rate = 0.0
            self.ore_stock.lower_threshold = c.target_ore_stock_level
            self.ore1_stock.lower_threshold = 0.0
        elif mode == MineMode.SHUTDOWN:
            pass


class MineController(drs.Module):
    def __init__(self, config: MiningDRSConfig, plant: MinePlant):
        super().__init__()
        self.config = config
        self.plant = plant

        self.current_mode = drs.State("current_mode", MineMode.MODE_A)

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

        # TODO: do all DRS modules/models have registries? can we have a default one and it always calls _setup_registry() or something? like is there a way to do this where it doesnt need to be put every time?
        self.registry = StateMachine()
        self._setup_registry()

        self.current_mode.value = MineMode.MODE_A

    # TODO: should this be required?
    def _setup_registry(self):
        c = self.config
        plant = self.plant

        # ----------------------------------------------------
        # TRANSITIONS (Command Pattern for check_transitions)
        # ----------------------------------------------------
        # The registry defines the discrete event logic of the state machine.
        # We register transition rules that bind a specific trigger (e.g., a timer reaching its upper bound,
        # or a level hitting its lower bound) to a target mode or a side-effect function.
        # Note: In this refactored version, the continuous dynamics (rate assignments) are handled via
        # explicit if/else blocks in the `update_rates` methods, rather than being registered here.

        # Upper timer logic for coming out of shutdown
        def end_of_shutdown():
            self.time_executed_campaign_shutdown.reset()
            if plant.ore2_stock.value > c.critical_ore2_level:
                if plant.ore_stock.value <= c.target_ore_stock_level:
                    return MineMode.MODE_A
                else:
                    return MineMode.MODE_A_MINE_SURGING
            else:
                if plant.ore_stock.value <= c.target_ore_stock_level:
                    return MineMode.MODE_B
                else:
                    return MineMode.MODE_B_MINE_SURGING

        def end_of_campaign():
            self.time_executed_campaign_shutdown.reset()
            return MineMode.SHUTDOWN

        def begin_contingency_a():
            self.time_executed_contingency.reset()
            return MineMode.MODE_A_CONTINGENCY

        def begin_contingency_b():
            self.time_executed_contingency.reset()
            return MineMode.MODE_B_CONTINGENCY

        def end_of_contingency_a():
            return MineMode.MODE_A

        def end_of_contingency_b():
            return MineMode.MODE_B

        # Non-mode transitions (Side effect functions)
        def generate_parcel_action():
            plant._generate_next_parcel()
            return None  # no mode transition

        def reset_timers_action():
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
            return None  # no mode transition

        # Register transitions across all modes
        for mode in MineMode:
            # Shared timer rules
            if mode != MineMode.SHUTDOWN:
                self.registry.register_transition(
                    source=mode,
                    trigger=self.time_executed_campaign_shutdown.upper_bound,
                    target=end_of_campaign,
                )
            else:
                self.registry.register_transition(
                    source=mode,
                    trigger=self.time_executed_campaign_shutdown.upper_bound,
                    target=end_of_shutdown,
                )

            # Shared level rules (side-effects on upper thresholds)
            self.registry.register_transition(
                source=mode,
                trigger=plant.ore_extracted_from_current_parcel.upper_bound,
                target=generate_parcel_action,
            )
            self.registry.register_transition(
                source=mode,
                trigger=plant.ore_extraction.upper_bound,
                target=reset_timers_action,
            )

        # Mode-specific timer rules
        self.registry.register_transition(
            source=MineMode.MODE_A_CONTINGENCY,
            trigger=self.time_executed_contingency.upper_bound,
            target=end_of_contingency_a,
        )
        self.registry.register_transition(
            source=MineMode.MODE_B_CONTINGENCY,
            trigger=self.time_executed_contingency.upper_bound,
            target=end_of_contingency_b,
        )

        # Level Lower-bound mode changes
        self.registry.register_transition(
            source=MineMode.MODE_A_MINE_SURGING,
            trigger=plant.ore_stock.lower_bound,
            target=MineMode.MODE_A,
        )
        self.registry.register_transition(
            source=MineMode.MODE_B_MINE_SURGING,
            trigger=plant.ore_stock.lower_bound,
            target=MineMode.MODE_B,
        )

        self.registry.register_transition(
            source=MineMode.MODE_A,
            trigger=plant.ore1_stock.lower_bound,
            target=MineMode.MODE_A_MINE_SURGING,
        )
        self.registry.register_transition(
            source=MineMode.MODE_A_CONTINGENCY,
            trigger=plant.ore1_stock.lower_bound,
            target=MineMode.MODE_A_MINE_SURGING,
        )
        self.registry.register_transition(
            source=MineMode.MODE_B,
            trigger=plant.ore1_stock.lower_bound,
            target=begin_contingency_b,
        )

        self.registry.register_transition(
            source=MineMode.MODE_A,
            trigger=plant.ore2_stock.lower_bound,
            target=begin_contingency_a,
        )
        self.registry.register_transition(
            source=MineMode.MODE_B,
            trigger=plant.ore2_stock.lower_bound,
            target=MineMode.MODE_B_MINE_SURGING,
        )
        self.registry.register_transition(
            source=MineMode.MODE_B_CONTINGENCY,
            trigger=plant.ore2_stock.lower_bound,
            target=MineMode.MODE_B_MINE_SURGING,
        )

    def update_rates(self):
        m = self.current_mode.value

        if m == MineMode.MODE_A:
            self.time_mode_a.rate = 1.0
        elif m == MineMode.MODE_A_CONTINGENCY:
            self.time_mode_a_contingency.rate = 1.0
            self.time_executed_contingency.rate = 1.0
            self.time_executed_contingency.upper_threshold = (
                self.config.duration_of_contingency_segments
            )
        elif m == MineMode.MODE_A_MINE_SURGING:
            self.time_mode_a_surging.rate = 1.0
        elif m == MineMode.MODE_B:
            self.time_mode_b.rate = 1.0
        elif m == MineMode.MODE_B_CONTINGENCY:
            self.time_mode_b_contingency.rate = 1.0
            self.time_executed_contingency.rate = 1.0
            self.time_executed_contingency.upper_threshold = (
                self.config.duration_of_contingency_segments
            )
        elif m == MineMode.MODE_B_MINE_SURGING:
            self.time_mode_b_surging.rate = 1.0
        elif m == MineMode.SHUTDOWN:
            self.time_shutdown.rate = 1.0

        self.time_executed_campaign_shutdown.rate = 1.0

        if m == MineMode.SHUTDOWN:
            self.time_executed_campaign_shutdown.upper_threshold = (
                self.config.duration_of_shutdowns
            )
        else:
            self.time_executed_campaign_shutdown.upper_threshold = (
                self.config.duration_of_production_campaigns
            )

    def check_transitions(
        self, trigger_var: drs.Variable = None, is_upper: bool = True
    ):
        next_mode = self.registry.get_next_mode(
            self.current_mode.value, trigger_var, is_upper=is_upper
        )
        if next_mode:
            self.current_mode.value = next_mode


class ExampleMineModel(drs.Module):
    def __init__(self, config: MiningDRSConfig):
        super().__init__()
        self.config = config

        self.plant = MinePlant(config)
        self.controller = MineController(config, self.plant)

        self.telemetry = Telemetry(self)
        self.telemetry.register_metric(
            "MassOfCurrentParcel_State",
            lambda t, m, s, h: m.plant.mass_of_current_parcel,
        )
        self.telemetry.register_metric(
            "PercentageOfOre2_State", lambda t, m, s, h: m.plant.percentage_of_ore2
        )
        self.telemetry.register_metric(
            "Campaign_Shutdown_Timer",
            lambda t, m, s, h: m.controller.time_executed_campaign_shutdown.value,
        )
        self.telemetry.register_metric(
            "Contingency_Timer",
            lambda t, m, s, h: m.controller.time_executed_contingency.value,
        )

    def update_rates(self):
        self.controller.update_rates()
        self.plant.update_rates(self.controller.current_mode.value)

    def check_transitions(
        self, trigger_var: drs.Variable = None, is_upper: bool = True
    ):
        self.controller.check_transitions(trigger_var, is_upper)

    def is_terminating_condition_met(self) -> bool:
        c = self.config
        extraction_met = self.plant.ore_extraction.value >= c.total_ore_to_extract
        stock_met = abs(self.plant.ore_stock.value - c.target_ore_stock_level) < 0.001

        return extraction_met and stock_met

    def print_statistics(self):
        print("\n--- Output Statistics ---")

        # Calculate Total Time
        total_time = (
            self.controller.time_mode_a.value
            + self.controller.time_mode_a_contingency.value
            + self.controller.time_mode_a_surging.value
            + self.controller.time_mode_b.value
            + self.controller.time_mode_b_contingency.value
            + self.controller.time_mode_b_surging.value
            + self.controller.time_shutdown.value
        )

        if total_time > 0:
            print(
                f"PortionOfTimeInModeA: {self.controller.time_mode_a.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeAContingency: {self.controller.time_mode_a_contingency.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeAMineSurging: {self.controller.time_mode_a_surging.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeB: {self.controller.time_mode_b.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeBContingency: {self.controller.time_mode_b_contingency.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeBMineSurging: {self.controller.time_mode_b_surging.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInShutdown: {self.controller.time_shutdown.value / total_time:.4f}"
            )
        else:
            print("Total time is 0. Cannot calculate mode portions.")

        # Calculate Throughput
        active_time = total_time - self.controller.time_shutdown.value
        if active_time > 0:
            throughput = (
                self.plant.ore_extraction.value
                - self.config.ore_to_be_extracted_during_warming_period
            ) / active_time
            print(f"Throughput: {throughput:.4f} tons/day")
        else:
            print("Active time is 0. Cannot calculate throughput.")


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # Ensure reproducibility for the example to guarantee it runs exactly the same
    # TODO: seed 11 shows behaviour where Total Ore Stockpile Level goes above target. how should htis be handled? stop production (ie a higher threshold? or its okay for the stockpile to go up like that?)
    random.seed(11)

    config = MiningDRSConfig(
        replication_length=99999.0,
    )
    sim = ExampleMineModel(config)

    # Engine is pure and acts on the module
    engine = DRSEngine(sim)
    engine.run(max_time=config.replication_length)

    sim.print_statistics()

    df = sim.telemetry.to_dataframe()

    # --- Mode Transition Log ---
    print("\n--- Mode Transition Log ---")
    df["prev_mode"] = df["current_mode"].shift(1)
    transitions = df[(df["current_mode"] != df["prev_mode"]) & df["prev_mode"].notna()]

    for idx, row in transitions.iterrows():
        try:
            prev = row["prev_mode"].value
            curr = row["current_mode"].value
        except AttributeError:
            prev = row["prev_mode"]
            curr = row["current_mode"]

        print(f"Time: {row['time']:.2f} | Transition: {prev} -> {curr}")
        print(
            f"  ↳ Ore1 Stock: {row['Ore1Stock_Level']:.1f} | Ore2 Stock: {row['Ore2Stock_Level']:.1f} (Critical: {config.critical_ore2_level}) | Total Stock: {row['OreStock_Level']:.1f} (Target: {config.target_ore_stock_level})"
        )
        print(
            f"  ↳ Campaign/Shutdown Timer: {row['TimeExecutedInCurrentCampaignOrShutdown_Timer']:.2f} | Contingency Timer: {row['TimeExecutedInCurrentContingencySegment_Timer']:.2f}"
        )
    print("---------------------------\n")

    # --- Cumulative Deficit by Mode Log ---
    import pandas as pd

    dt = df["time"].diff().fillna(0)
    actual_extraction_step = df["OreExtraction_Level"].diff().fillna(0)
    ideal_extraction_step = dt * 6000.0
    step_deficit = (ideal_extraction_step - actual_extraction_step).clip(lower=0)

    deficit_df = pd.DataFrame(
        {"mode": df["current_mode"].astype(str), "deficit": step_deficit}
    )

    total_deficit_by_mode = (
        deficit_df.groupby("mode")["deficit"].sum().sort_values(ascending=False)
    )

    print("\n--- Cumulative Lost Production (Deficit) by Mode ---")
    total_lost = total_deficit_by_mode.sum()
    for mode, lost in total_deficit_by_mode.items():
        mode_name = str(mode).split(".")[-1]
        pct = (lost / total_lost * 100) if total_lost > 0 else 0
        print(f"{mode_name}: {lost:.1f} tons ({pct:.1f}%)")
    print(f"TOTAL: {total_lost:.1f} tons")
    print("----------------------------------------------------\n")

    # Create Modes Series
    df["Mode A"] = df["current_mode"].apply(
        lambda m: (
            3
            if m
            in (
                MineMode.MODE_A,
                MineMode.MODE_A_CONTINGENCY,
                MineMode.MODE_A_MINE_SURGING,
            )
            else 0
        )
    )
    df["Mode B"] = df["current_mode"].apply(
        lambda m: (
            2
            if m
            in (
                MineMode.MODE_B,
                MineMode.MODE_B_CONTINGENCY,
                MineMode.MODE_B_MINE_SURGING,
            )
            else 0
        )
    )
    df["Shutdown"] = df["current_mode"].apply(
        lambda m: 1 if m == MineMode.SHUTDOWN else 0
    )

    # Create Ore Level Series (scaled by 1000)
    df["Total Ore Stockpile Level"] = df["OreStock_Level"] / 1000.0
    df["Ore 1 Stockpile Level"] = df["Ore1Stock_Level"] / 1000.0
    df["Ore 2 Stockpile Level"] = df["Ore2Stock_Level"] / 1000.0

    from mining_drs.plot import (
        plot_time_series,
        plot_ore_with_modes,
        plot_dual_axis_step,
        plot_safety_margin,
        plot_state_space,
        plot_mode_distribution,
        plot_cumulative_throughput,
        plot_mode_dwell_times,
        plot_normalized_deviation_violin,
        plot_attributed_deficit,
        plot_deficit_disparity,
        plot_deficit_breakdown_bar,
        plot_structural_vs_operational_deficit,
        plot_normalized_cumulative_deficit,
        plot_structural_vs_operational_by_mode,
        build_dashboard,
    )

    configs = [
        {
            "func": plot_time_series,
            "kwargs": {
                "y_columns": ["Mode A", "Mode B", "Shutdown"],
                "title": "Modes (Step)",
                "is_step": True,
            },
        },
        {
            "func": plot_ore_with_modes,
            "kwargs": {
                "time_col": "time",
                "ore_cols": ["OreStock_Level", "Ore1Stock_Level", "Ore2Stock_Level"],
                "mode_col": "current_mode",
                "campaign_split_mode": MineMode.SHUTDOWN,
                "title": "Ore Stockpiles & Campaigns",
                "hlines": [
                    {
                        "y": 60000,
                        "color": "black",
                        "linestyle": "--",
                        "linewidth": 1.5,
                        "alpha": 0.7,
                        "label": "Target Total (60k)",
                    },
                    {
                        "y": 20400,
                        "color": "red",
                        "linestyle": ":",
                        "linewidth": 2,
                        "alpha": 0.8,
                        "label": "Critical Ore 2 (20.4k)",
                    },
                ],
            },
        },
        {
            "func": plot_dual_axis_step,
            "kwargs": {
                "y1_col": "MassOfCurrentParcel_State",
                "y2_col": "PercentageOfOre2_State",
                "y1_label": "Parcel Mass (tons)",
                "y2_label": "Grade (% Ore 2)",
                "title": "Current Parcel Properties",
            },
        },
        {
            "func": plot_safety_margin,
            "kwargs": {
                "level_col": "Ore1Stock_Level",
                "constraint_value": 0.0,
                "constraint_type": "lower",
                "title": "Safety Margin: Ore 1 Distance to Floor",
                "danger_threshold": 1000.0,
            },
        },
        {
            "func": plot_safety_margin,
            "kwargs": {
                "level_col": "Ore2Stock_Level",
                "constraint_value": 0.0,
                "constraint_type": "lower",
                "title": "Safety Margin: Ore 2 Distance to Floor",
                "danger_threshold": 1000.0,
            },
        },
        {
            "func": plot_mode_distribution,
            "kwargs": {
                "mode_col": "current_mode",
                "time_col": "time",
                "title": "Mode Distribution (% of Time Spent)",
            },
        },
        {
            "func": plot_mode_dwell_times,
            "kwargs": {
                "time_col": "time",
                "mode_col": "current_mode",
                "title": "Mode Stability (Dwell Times)",
            },
        },
        {
            "func": plot_normalized_deviation_violin,
            "kwargs": {
                "title": "Stockpile Deviation Variance (Violin)",
            },
        },
        {
            "func": plot_attributed_deficit,
            "kwargs": {
                "time_col": "time",
                "mode_col": "current_mode",
                "extraction_col": "OreExtraction_Level",
                "ideal_rate_per_day": 6000.0,
                "title": "Cumulative Production Deficit by Mode",
            },
        },
        {
            "func": plot_deficit_disparity,
            "kwargs": {
                "title": "Mode Efficiency (Time Spent vs. Deficit Caused)",
            },
        },
        {
            "func": plot_deficit_breakdown_bar,
            "kwargs": {},
        },
        {
            "func": plot_structural_vs_operational_deficit,
            "kwargs": {},
        },
        {
            "func": plot_normalized_cumulative_deficit,
            "kwargs": {},
        },
        {
            "func": plot_structural_vs_operational_by_mode,
            "kwargs": {},
        },
    ]

    fig_comp = build_dashboard(
        df, configs, title="Comprehensive Mine Diagnostics", figsize=(18, 69)
    )
    fig_comp.savefig("Comprehensive_Diagnostics_Plot.png")
