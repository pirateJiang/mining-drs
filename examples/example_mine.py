import math
import random
from enum import Enum
from mining_drs.engine import DRSEngine
from mining_drs.variables import Level, Timer
from mining_drs.config import MiningDRSConfig
from mining_drs.telemetry import Telemetry


class MineMode(Enum):
    MODE_A = "ModeA"
    MODE_A_CONTINGENCY = "ModeAContingency"
    MODE_A_MINE_SURGING = "ModeAMineSurging"
    MODE_B = "ModeB"
    MODE_B_CONTINGENCY = "ModeBContingency"
    MODE_B_MINE_SURGING = "ModeBMineSurging"
    SHUTDOWN = "Shutdown"


class ExampleMineModel(DRSEngine):
    def __init__(self, config: MiningDRSConfig):
        super().__init__()
        self.config = config
        self.telemetry = Telemetry(self)
        self.current_mode = MineMode.MODE_A
        self.next_event_trigger = None

        # Geostatistical Parameters
        self.min_ore_mass = 30000.0
        self.max_ore_mass = 50000.0
        self.prob_new_facies = 0.3
        self.mean_grade_new_facies = 30.0
        self.std_dev_new_facies = 5.0
        self.variation_same_facies = 1.0

        # Parcel State
        self.mass_of_current_parcel = 40000.0
        self.percentage_of_ore2 = 30.0
        self.next_parcel_is_new_facies = True

    def initialize_state(self):
        # Initial Level Values
        self.ore_extraction = Level("OreExtraction_Level", initial_value=0.0)
        self.ore_extracted_from_current_parcel = Level(
            "OreExtractedFromCurrentParcel_Level", initial_value=0.0
        )
        self.ore_stock = Level(
            "OreStock_Level", initial_value=self.config.target_ore_stock_level
        )
        self.ore1_stock = Level(
            "Ore1Stock_Level",
            initial_value=(1 - 0.3) * self.config.target_ore_stock_level,
        )
        self.ore2_stock = Level(
            "Ore2Stock_Level", initial_value=0.3 * self.config.target_ore_stock_level
        )

        # Initial Timer Values
        self.time_executed_campaign_shutdown = Timer(
            "TimeExecutedInCurrentCampaignOrShutdown_Timer", initial_value=0.0
        )
        self.time_executed_contingency = Timer(
            "TimeExecutedInCurrentContingencySegment_Timer", initial_value=0.0
        )
        self.time_mode_a = Timer("TimeInModeA_Timer", initial_value=0.0)
        self.time_mode_a_contingency = Timer(
            "TimeInModeAContingency_Timer", initial_value=0.0
        )
        self.time_mode_a_surging = Timer("TimeInModeAMineSurging_Timer", initial_value=0.0)
        self.time_mode_b = Timer("TimeInModeB_Timer", initial_value=0.0)
        self.time_mode_b_contingency = Timer(
            "TimeInModeBContingency_Timer", initial_value=0.0
        )
        self.time_mode_b_surging = Timer("TimeInModeBMineSurging_Timer", initial_value=0.0)
        self.time_shutdown = Timer("TimeInShutdown_Level", initial_value=0.0)

        self.levels = [
            self.ore_extraction,
            self.ore_extracted_from_current_parcel,
            self.ore_stock,
            self.ore1_stock,
            self.ore2_stock,
        ]

        self.timers = [
            self.time_executed_campaign_shutdown,
            self.time_executed_contingency,
            self.time_mode_a,
            self.time_mode_a_contingency,
            self.time_mode_a_surging,
            self.time_mode_b,
            self.time_mode_b_contingency,
            self.time_mode_b_surging,
            self.time_shutdown,
        ]

        self.variables = self.levels + self.timers

        self.apply_mode(MineMode.MODE_A)

    def _set_rates(self):
        c = self.config
        p_ore2 = self.percentage_of_ore2

        # Reset rates to 0
        for var in self.variables:
            var.rate = 0.0

        if self.current_mode == MineMode.MODE_A:
            rate = c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate
            self.ore_extraction.rate = rate
            self.ore_extracted_from_current_parcel.rate = rate
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = rate * (1 - p_ore2 / 100) - c.mode_a_ore1_milling_rate
            self.ore2_stock.rate = rate * (p_ore2 / 100) - c.mode_a_ore2_milling_rate
            self.time_mode_a.rate = 1.0

        elif self.current_mode == MineMode.MODE_A_CONTINGENCY:
            rate = c.mode_a_contingency_ore1_milling_rate
            self.ore_extraction.rate = rate
            self.ore_extracted_from_current_parcel.rate = rate
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = rate * (1 - p_ore2 / 100) - rate
            self.ore2_stock.rate = rate * (p_ore2 / 100)
            self.time_executed_contingency.rate = 1.0
            self.time_mode_a_contingency.rate = 1.0

        elif self.current_mode == MineMode.MODE_A_MINE_SURGING:
            rate = c.mode_a_ore1_milling_rate * 100 / (100 - p_ore2)
            self.ore_extraction.rate = rate
            self.ore_extracted_from_current_parcel.rate = rate
            self.ore_stock.rate = rate - c.mode_a_ore1_milling_rate - c.mode_a_ore2_milling_rate
            self.ore1_stock.rate = 0.0
            self.ore2_stock.rate = rate * (p_ore2 / 100) - c.mode_a_ore2_milling_rate
            self.time_mode_a_surging.rate = 1.0

        elif self.current_mode == MineMode.MODE_B:
            rate = c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate
            self.ore_extraction.rate = rate
            self.ore_extracted_from_current_parcel.rate = rate
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = rate * (100 - p_ore2) / 100 - c.mode_b_ore1_milling_rate
            self.ore2_stock.rate = rate * (p_ore2 / 100) - c.mode_b_ore2_milling_rate
            self.time_mode_b.rate = 1.0

        elif self.current_mode == MineMode.MODE_B_CONTINGENCY:
            rate = c.mode_b_contingency_ore2_milling_rate
            self.ore_extraction.rate = rate
            self.ore_extracted_from_current_parcel.rate = rate
            self.ore_stock.rate = 0.0
            self.ore1_stock.rate = rate * (100 - p_ore2) / 100
            self.ore2_stock.rate = rate * (p_ore2 / 100) - rate
            self.time_executed_contingency.rate = 1.0
            self.time_mode_b_contingency.rate = 1.0

        elif self.current_mode == MineMode.MODE_B_MINE_SURGING:
            rate = c.mode_b_ore2_milling_rate * 100 / p_ore2
            self.ore_extraction.rate = rate
            self.ore_extracted_from_current_parcel.rate = rate
            self.ore_stock.rate = rate - c.mode_b_ore1_milling_rate - c.mode_b_ore2_milling_rate
            self.ore1_stock.rate = rate * (100 - p_ore2) / 100 - c.mode_b_ore1_milling_rate
            self.ore2_stock.rate = 0.0
            self.time_mode_b_surging.rate = 1.0

        elif self.current_mode == MineMode.SHUTDOWN:
            self.time_shutdown.rate = 1.0

        # Shared rates
        self.time_executed_campaign_shutdown.rate = 1.0

    def _set_thresholds(self):
        c = self.config
        # Clean up existing thresholds
        for var in self.variables:
            if hasattr(var, "upper_threshold"):
                delattr(var, "upper_threshold")
            if hasattr(var, "lower_threshold"):
                delattr(var, "lower_threshold")

        # Ore Extraction (upper)
        if self.ore_extraction.value < c.ore_to_be_extracted_during_warming_period:
            self.ore_extraction.upper_threshold = c.ore_to_be_extracted_during_warming_period
        else:
            self.ore_extraction.upper_threshold = c.total_ore_to_extract

        # Parcel Extraction (upper)
        if self.current_mode != MineMode.SHUTDOWN:
            self.ore_extracted_from_current_parcel.upper_threshold = self.mass_of_current_parcel

        # Stocks (lower)
        if self.current_mode in (MineMode.MODE_A_MINE_SURGING, MineMode.MODE_B_MINE_SURGING):
            self.ore_stock.lower_threshold = c.target_ore_stock_level
        if self.current_mode in (MineMode.MODE_A, MineMode.MODE_A_CONTINGENCY, MineMode.MODE_B):
            self.ore1_stock.lower_threshold = 0.0
        # Fix: MODE_A typo
        if self.current_mode in (MineMode.MODE_A, MineMode.MODE_B, MineMode.MODE_B_CONTINGENCY):
            self.ore2_stock.lower_threshold = 0.0

        # Timers (upper)
        if self.current_mode == MineMode.SHUTDOWN:
            self.time_executed_campaign_shutdown.upper_threshold = c.duration_of_shutdowns
        else:
            self.time_executed_campaign_shutdown.upper_threshold = c.duration_of_production_campaigns

        if self.current_mode in (MineMode.MODE_A_CONTINGENCY, MineMode.MODE_B_CONTINGENCY):
            self.time_executed_contingency.upper_threshold = c.duration_of_contingency_segments

    def apply_mode(self, mode: MineMode):
        self.current_mode = mode
        self._set_rates()
        self._set_thresholds()

    def is_terminating_condition_met(self) -> bool:
        c = self.config
        extraction_met = self.ore_extraction.value >= c.total_ore_to_extract
        stock_met = abs(self.ore_stock.value - c.target_ore_stock_level) < 0.001
        time_limit = self.current_time >= c.replication_length

        return (extraction_met and stock_met) or time_limit

    def calculate_time_to_next_threshold(self) -> float:
        min_dt = math.inf
        self.next_event_trigger = None
        self.next_event_is_upper = True

        # Need to recalculate thresholds since variables changed values
        self._set_thresholds()

        for var in self.variables:
            dt_for_var = math.inf
            is_upper = True

            if var.rate > 0 and hasattr(var, "upper_threshold"):
                dt_for_var = (var.upper_threshold - var.value) / var.rate
            elif var.rate < 0 and hasattr(var, "lower_threshold"):
                dt_for_var = (var.value - var.lower_threshold) / abs(var.rate)
                is_upper = False

            if 1e-9 < dt_for_var < min_dt:
                min_dt = dt_for_var
                self.next_event_trigger = var
                self.next_event_is_upper = is_upper

        if min_dt == math.inf:
            return 1.0

        return min_dt

    def check_and_trigger_thresholds(self):
        var = self.next_event_trigger
        is_upper = self.next_event_is_upper

        # 1. Timers
        if var == self.time_executed_campaign_shutdown and is_upper:
            self.time_executed_campaign_shutdown.reset()
            if self.current_mode != MineMode.SHUTDOWN:
                self.apply_mode(MineMode.SHUTDOWN)
            else:
                # Coming out of shutdown
                if self.ore2_stock.value > self.config.critical_ore2_level:
                    if self.ore_stock.value <= self.config.target_ore_stock_level:
                        self.apply_mode(MineMode.MODE_A)
                    else:
                        self.apply_mode(MineMode.MODE_A_MINE_SURGING)
                else:
                    if self.ore_stock.value <= self.config.target_ore_stock_level:
                        self.apply_mode(MineMode.MODE_B)
                    else:
                        self.apply_mode(MineMode.MODE_B_MINE_SURGING)

        elif var == self.time_executed_contingency and is_upper:
            self.time_executed_contingency.reset()
            if self.current_mode == MineMode.MODE_A_CONTINGENCY:
                self.apply_mode(MineMode.MODE_A)
            elif self.current_mode == MineMode.MODE_B_CONTINGENCY:
                self.apply_mode(MineMode.MODE_B)

        # 2. Levels (Lower)
        elif var == self.ore_stock and not is_upper:
            if self.current_mode == MineMode.MODE_A_MINE_SURGING:
                self.apply_mode(MineMode.MODE_A)
            elif self.current_mode == MineMode.MODE_B_MINE_SURGING:
                self.apply_mode(MineMode.MODE_B)

        elif var == self.ore1_stock and not is_upper:
            if self.current_mode in (MineMode.MODE_A, MineMode.MODE_A_CONTINGENCY):
                self.apply_mode(MineMode.MODE_A_MINE_SURGING)
            elif self.current_mode == MineMode.MODE_B:
                self.apply_mode(MineMode.MODE_B_CONTINGENCY)

        elif var == self.ore2_stock and not is_upper:
            if self.current_mode == MineMode.MODE_A:
                self.apply_mode(MineMode.MODE_A_CONTINGENCY)
            elif self.current_mode in (MineMode.MODE_B, MineMode.MODE_B_CONTINGENCY):
                self.apply_mode(MineMode.MODE_B_MINE_SURGING)

        # 3. Levels (Upper)
        elif var == self.ore_extraction and is_upper:
            if abs(self.ore_extraction.value - self.config.ore_to_be_extracted_during_warming_period) < 0.1:
                # End of warmup - reset all mode timers
                self.time_mode_a.reset()
                self.time_mode_a_contingency.reset()
                self.time_mode_a_surging.reset()
                self.time_mode_b.reset()
                self.time_mode_b_contingency.reset()
                self.time_mode_b_surging.reset()
                self.time_shutdown.reset()

        elif var == self.ore_extracted_from_current_parcel and is_upper:
            self._generate_next_parcel()

        # Recalculate rates/thresholds
        self._set_rates()
        self._set_thresholds()

    def _generate_next_parcel(self):
        self.ore_extracted_from_current_parcel.value = 0.0
        self.mass_of_current_parcel = random.uniform(self.min_ore_mass, self.max_ore_mass)

        if self.next_parcel_is_new_facies:
            if self.std_dev_new_facies != 0:
                val = random.gauss(self.mean_grade_new_facies, self.std_dev_new_facies)
            else:
                val = self.mean_grade_new_facies
            self.percentage_of_ore2 = max(val, 0.0)
        else:
            val = self.percentage_of_ore2 + self.variation_same_facies * random.uniform(-1, 1)
            self.percentage_of_ore2 = max(val, 0.0)

        self.next_parcel_is_new_facies = random.random() <= self.prob_new_facies

    def record_statistics(self):
        self.telemetry.snapshot(self.current_time)
        self.telemetry.history[-1]["current_mode"] = self.current_mode.value


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    config = MiningDRSConfig(
        replication_length=99999.0,
    )
    sim = ExampleMineModel(config)
    sim.run()

    df = sim.telemetry.to_dataframe()

    # Create Modes Series
    df["Mode A"] = df["current_mode"].apply(
        lambda m: 3 if m in (MineMode.MODE_A.value, MineMode.MODE_A_CONTINGENCY.value, MineMode.MODE_A_MINE_SURGING.value) else 0
    )
    df["Mode B"] = df["current_mode"].apply(
        lambda m: 2 if m in (MineMode.MODE_B.value, MineMode.MODE_B_CONTINGENCY.value, MineMode.MODE_B_MINE_SURGING.value) else 0
    )
    df["Shutdown"] = df["current_mode"].apply(
        lambda m: 1 if m == MineMode.SHUTDOWN.value else 0
    )

    # Create Ore Level Series (scaled by 1000)
    df["Total Ore Stockpile Level"] = df["OreStock_Level"] / 1000.0
    df["Ore 1 Stockpile Level"] = df["Ore1Stock_Level"] / 1000.0
    df["Ore 2 Stockpile Level"] = df["Ore2Stock_Level"] / 1000.0

    plt.style.use('seaborn-v0_8-whitegrid')

    # Plot 1: Modes Plot
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    ax1.step(df["time"], df["Mode A"], where='post', label="Mode A", linewidth=2)
    ax1.step(df["time"], df["Mode B"], where='post', label="Mode B", linewidth=2)
    ax1.step(df["time"], df["Shutdown"], where='post', label="Shutdown", linewidth=2)
    
    ax1.set_title("Modes Plot", fontsize=14, pad=15)
    ax1.set_xlabel("Time (Days)", fontsize=12)
    ax1.set_ylabel("Mode State", fontsize=12)
    ax1.set_xlim(0, 1000)
    ax1.set_ylim(0, 4)
    ax1.set_yticks([0, 1, 2, 3, 4])
    ax1.legend(loc='upper right', bbox_to_anchor=(1, 1.1), ncol=3, frameon=True)
    fig1.tight_layout()
    fig1.savefig("Modes_Plot.png")

    # Plot 2: Ore Level Plot
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    ax2.plot(df["time"], df["Total Ore Stockpile Level"], label="Total Ore Stockpile Level", linewidth=2)
    ax2.plot(df["time"], df["Ore 1 Stockpile Level"], label="Ore 1 Stockpile Level", linewidth=2)
    ax2.plot(df["time"], df["Ore 2 Stockpile Level"], label="Ore 2 Stockpile Level", color="pink", linewidth=2)
    
    ax2.set_title("Ore Level Plot", fontsize=14, pad=15)
    ax2.set_xlabel("Time (Days)", fontsize=12)
    ax2.set_ylabel("Ore Level (Thousands of Tons)", fontsize=12)
    ax2.set_xlim(0, 1000)
    ax2.set_ylim(0, 80)
    ax2.set_yticks([0, 10, 20, 30, 40, 50, 60, 70, 80])
    ax2.legend(loc='upper right', bbox_to_anchor=(1, 1.1), ncol=3, frameon=True)
    fig2.tight_layout()
    fig2.savefig("Ore_Level_Plot.png")
