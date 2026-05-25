import math
import random
from enum import Enum
from mining_drs import drs, DRSEngine
from mining_drs.config import MiningDRSConfig
from mining_drs.telemetry import Telemetry
from mining_drs.modes import SequenceRegistry


class MineMode(Enum):
    MODE_A = "ModeA"
    MODE_A_CONTINGENCY = "ModeAContingency"
    MODE_A_MINE_SURGING = "ModeAMineSurging"
    MODE_B = "ModeB"
    MODE_B_CONTINGENCY = "ModeBContingency"
    MODE_B_MINE_SURGING = "ModeBMineSurging"
    SHUTDOWN = "Shutdown"


class ExampleMineModel(drs.Module):
    def __init__(self, config: MiningDRSConfig):
        super().__init__()
        self.config = config
        self.telemetry = Telemetry(self)
        self.current_mode = MineMode.MODE_A

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
            initial_value=(1 - (self.config.mean_grade_new_facies / 100.0)) * self.config.target_ore_stock_level,
        )
        self.ore2_stock = drs.Level(
            "Ore2Stock_Level", initial_value=(self.config.mean_grade_new_facies / 100.0) * self.config.target_ore_stock_level
        )

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
        self.time_mode_a_surging = drs.Timer("TimeInModeAMineSurging_Timer", initial_value=0.0)
        self.time_mode_b = drs.Timer("TimeInModeB_Timer", initial_value=0.0)
        self.time_mode_b_contingency = drs.Timer(
            "TimeInModeBContingency_Timer", initial_value=0.0
        )
        self.time_mode_b_surging = drs.Timer("TimeInModeBMineSurging_Timer", initial_value=0.0)
        self.time_shutdown = drs.Timer("TimeInShutdown_Level", initial_value=0.0)

        self.registry = SequenceRegistry()
        self._setup_registry()

        self.apply_mode(MineMode.MODE_A)

    def _setup_registry(self):
        c = self.config
        
        # ----------------------------------------------------
        # RATE ASSIGNMENT SEQUENCES (Command Pattern)
        # ----------------------------------------------------
        def rate_seq_mode_a(ctx):
            r = c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate
            p = ctx.percentage_of_ore2
            ctx.ore_extraction.rate = r
            ctx.ore_extracted_from_current_parcel.rate = r
            ctx.ore_stock.rate = 0.0
            ctx.ore1_stock.rate = r * (1 - p / 100) - c.mode_a_ore1_milling_rate
            ctx.ore2_stock.rate = r * (p / 100) - c.mode_a_ore2_milling_rate
            ctx.time_mode_a.rate = 1.0

        def rate_seq_mode_a_contingency(ctx):
            r = c.mode_a_contingency_ore1_milling_rate
            p = ctx.percentage_of_ore2
            ctx.ore_extraction.rate = r
            ctx.ore_extracted_from_current_parcel.rate = r
            ctx.ore_stock.rate = 0.0
            ctx.ore1_stock.rate = r * (1 - p / 100) - r
            ctx.ore2_stock.rate = r * (p / 100)
            ctx.time_mode_a_contingency.rate = 1.0
            ctx.time_executed_contingency.rate = 1.0

        def rate_seq_mode_a_surging(ctx):
            p = ctx.percentage_of_ore2
            r = c.mode_a_ore1_milling_rate * 100 / (100 - p)
            ctx.ore_extraction.rate = r
            ctx.ore_extracted_from_current_parcel.rate = r
            ctx.ore_stock.rate = r - c.mode_a_ore1_milling_rate - c.mode_a_ore2_milling_rate
            ctx.ore1_stock.rate = 0.0
            ctx.ore2_stock.rate = r * (p / 100) - c.mode_a_ore2_milling_rate
            ctx.time_mode_a_surging.rate = 1.0

        def rate_seq_mode_b(ctx):
            r = c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate
            p = ctx.percentage_of_ore2
            ctx.ore_extraction.rate = r
            ctx.ore_extracted_from_current_parcel.rate = r
            ctx.ore_stock.rate = 0.0
            ctx.ore1_stock.rate = r * (100 - p) / 100 - c.mode_b_ore1_milling_rate
            ctx.ore2_stock.rate = r * (p / 100) - c.mode_b_ore2_milling_rate
            ctx.time_mode_b.rate = 1.0

        def rate_seq_mode_b_contingency(ctx):
            r = c.mode_b_contingency_ore2_milling_rate
            p = ctx.percentage_of_ore2
            ctx.ore_extraction.rate = r
            ctx.ore_extracted_from_current_parcel.rate = r
            ctx.ore_stock.rate = 0.0
            ctx.ore1_stock.rate = r * (100 - p) / 100
            ctx.ore2_stock.rate = r * (p / 100) - r
            ctx.time_mode_b_contingency.rate = 1.0
            ctx.time_executed_contingency.rate = 1.0

        def rate_seq_mode_b_surging(ctx):
            p = ctx.percentage_of_ore2
            r = c.mode_b_ore2_milling_rate * 100 / p
            ctx.ore_extraction.rate = r
            ctx.ore_extracted_from_current_parcel.rate = r
            ctx.ore_stock.rate = r - c.mode_b_ore1_milling_rate - c.mode_b_ore2_milling_rate
            ctx.ore1_stock.rate = r * (100 - p) / 100 - c.mode_b_ore1_milling_rate
            ctx.ore2_stock.rate = 0.0
            ctx.time_mode_b_surging.rate = 1.0

        def rate_seq_shutdown(ctx):
            ctx.time_shutdown.rate = 1.0

        self.registry.register(MineMode.MODE_A, rate_seq_mode_a)
        self.registry.register(MineMode.MODE_A_CONTINGENCY, rate_seq_mode_a_contingency)
        self.registry.register(MineMode.MODE_A_MINE_SURGING, rate_seq_mode_a_surging)
        self.registry.register(MineMode.MODE_B, rate_seq_mode_b)
        self.registry.register(MineMode.MODE_B_CONTINGENCY, rate_seq_mode_b_contingency)
        self.registry.register(MineMode.MODE_B_MINE_SURGING, rate_seq_mode_b_surging)
        self.registry.register(MineMode.SHUTDOWN, rate_seq_shutdown)

        # ----------------------------------------------------
        # TRANSITIONS (Command Pattern for check_transitions)
        # ----------------------------------------------------
        
        # Upper timer logic for coming out of shutdown
        def end_of_shutdown(ctx):
            ctx.time_executed_campaign_shutdown.reset()
            if ctx.ore2_stock.value > ctx.config.critical_ore2_level:
                if ctx.ore_stock.value <= ctx.config.target_ore_stock_level:
                    return MineMode.MODE_A
                else:
                    return MineMode.MODE_A_MINE_SURGING
            else:
                if ctx.ore_stock.value <= ctx.config.target_ore_stock_level:
                    return MineMode.MODE_B
                else:
                    return MineMode.MODE_B_MINE_SURGING

        def end_of_campaign(ctx):
            ctx.time_executed_campaign_shutdown.reset()
            return MineMode.SHUTDOWN
            
        def end_of_contingency_a(ctx):
            ctx.time_executed_contingency.reset()
            return MineMode.MODE_A
            
        def end_of_contingency_b(ctx):
            ctx.time_executed_contingency.reset()
            return MineMode.MODE_B

        # Non-mode transitions (Side effect functions)
        def generate_parcel_action(ctx):
            ctx._generate_next_parcel()
            return None # no mode transition

        def reset_timers_action(ctx):
            if abs(ctx.ore_extraction.value - ctx.config.ore_to_be_extracted_during_warming_period) < 0.1:
                ctx.time_mode_a.reset()
                ctx.time_mode_a_contingency.reset()
                ctx.time_mode_a_surging.reset()
                ctx.time_mode_b.reset()
                ctx.time_mode_b_contingency.reset()
                ctx.time_mode_b_surging.reset()
                ctx.time_shutdown.reset()
            return None # no mode transition

        # Register transitions across all modes
        for mode in MineMode:
            # Shared timer rules
            if mode != MineMode.SHUTDOWN:
                self.registry.register_transition(mode, end_of_campaign, self.time_executed_campaign_shutdown, is_upper=True)
            else:
                self.registry.register_transition(mode, end_of_shutdown, self.time_executed_campaign_shutdown, is_upper=True)

            # Shared level rules (side-effects on upper thresholds)
            self.registry.register_transition(mode, generate_parcel_action, self.ore_extracted_from_current_parcel, is_upper=True)
            self.registry.register_transition(mode, reset_timers_action, self.ore_extraction, is_upper=True)

        # Mode-specific timer rules
        self.registry.register_transition(MineMode.MODE_A_CONTINGENCY, end_of_contingency_a, self.time_executed_contingency, is_upper=True)
        self.registry.register_transition(MineMode.MODE_B_CONTINGENCY, end_of_contingency_b, self.time_executed_contingency, is_upper=True)

        # Level Lower-bound mode changes
        self.registry.register_transition(MineMode.MODE_A_MINE_SURGING, MineMode.MODE_A, self.ore_stock, is_upper=False)
        self.registry.register_transition(MineMode.MODE_B_MINE_SURGING, MineMode.MODE_B, self.ore_stock, is_upper=False)
        
        self.registry.register_transition(MineMode.MODE_A, MineMode.MODE_A_MINE_SURGING, self.ore1_stock, is_upper=False)
        self.registry.register_transition(MineMode.MODE_A_CONTINGENCY, MineMode.MODE_A_MINE_SURGING, self.ore1_stock, is_upper=False)
        self.registry.register_transition(MineMode.MODE_B, MineMode.MODE_B_CONTINGENCY, self.ore1_stock, is_upper=False)

        self.registry.register_transition(MineMode.MODE_A, MineMode.MODE_A_CONTINGENCY, self.ore2_stock, is_upper=False)
        self.registry.register_transition(MineMode.MODE_B, MineMode.MODE_B_MINE_SURGING, self.ore2_stock, is_upper=False)
        self.registry.register_transition(MineMode.MODE_B_CONTINGENCY, MineMode.MODE_B_MINE_SURGING, self.ore2_stock, is_upper=False)

    def update_rates(self):
        """The 'forward' pass. Defines how states interact."""
        # 1. Reset all rates to 0
        for var in self.variables():
            var.rate = 0.0

        # 2. Execute dynamic rate rules for current mode
        self.registry.execute(self.current_mode, self)

        # 3. Shared rate
        self.time_executed_campaign_shutdown.rate = 1.0

        # 4. Set thresholds
        self._set_thresholds()

    def _set_thresholds(self):
        c = self.config
        # Clean up existing thresholds by resetting them
        for var in self.variables():
            var.upper_threshold = math.inf
            var.lower_threshold = -math.inf

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
        self.update_rates()

    def check_transitions(self, trigger_var=None, is_upper=True):
        # The engine doesn't need to know the specific logic, it just asks the registry
        next_mode = self.registry.get_next_mode(
            self.current_mode, 
            trigger_var, 
            is_upper=is_upper,
            context=self
        )
        if next_mode:
            self.apply_mode(next_mode)
            
        # Ensure we recalculate rates and thresholds even if we didn't transition
        self.update_rates()

    def is_terminating_condition_met(self) -> bool:
        c = self.config
        extraction_met = self.ore_extraction.value >= c.total_ore_to_extract
        stock_met = abs(self.ore_stock.value - c.target_ore_stock_level) < 0.001

        return extraction_met and stock_met

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
            val = self.percentage_of_ore2 + c.variation_same_facies * random.uniform(-1, 1)
            self.percentage_of_ore2 = max(val, 0.0)

        self.next_parcel_is_new_facies = random.random() <= c.prob_new_facies

    def record_statistics(self, current_time: float):
        self.telemetry.snapshot(current_time)
        self.telemetry.history[-1]["current_mode"] = self.current_mode.value

    def print_statistics(self):
        print("\n--- Output Statistics ---")
        
        # Calculate Total Time
        total_time = (
            self.time_mode_a.value + self.time_mode_a_contingency.value + self.time_mode_a_surging.value +
            self.time_mode_b.value + self.time_mode_b_contingency.value + self.time_mode_b_surging.value +
            self.time_shutdown.value
        )
        
        if total_time > 0:
            print(f"PortionOfTimeInModeA: {self.time_mode_a.value / total_time:.4f}")
            print(f"PortionOfTimeInModeAContingency: {self.time_mode_a_contingency.value / total_time:.4f}")
            print(f"PortionOfTimeInModeAMineSurging: {self.time_mode_a_surging.value / total_time:.4f}")
            print(f"PortionOfTimeInModeB: {self.time_mode_b.value / total_time:.4f}")
            print(f"PortionOfTimeInModeBContingency: {self.time_mode_b_contingency.value / total_time:.4f}")
            print(f"PortionOfTimeInModeBMineSurging: {self.time_mode_b_surging.value / total_time:.4f}")
            print(f"PortionOfTimeInShutdown: {self.time_shutdown.value / total_time:.4f}")
        else:
            print("Total time is 0. Cannot calculate mode portions.")

        # Calculate Throughput
        active_time = total_time - self.time_shutdown.value
        if active_time > 0:
            throughput = (self.ore_extraction.value - self.config.ore_to_be_extracted_during_warming_period) / active_time
            print(f"Throughput: {throughput:.4f} tons/day")
        else:
            print("Active time is 0. Cannot calculate throughput.")


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    # Ensure reproducibility for the example to guarantee it runs exactly the same
    random.seed(42)

    config = MiningDRSConfig(
        replication_length=99999.0,
    )
    sim = ExampleMineModel(config)
    
    # Engine is pure and acts on the module
    engine = DRSEngine(sim)
    engine.run(max_time=config.replication_length)
    
    sim.print_statistics()

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
    ax2.set_ylim(0, 80)
    ax2.set_yticks([0, 10, 20, 30, 40, 50, 60, 70, 80])
    ax2.legend(loc='upper right', bbox_to_anchor=(1, 1.1), ncol=3, frameon=True)
    fig2.tight_layout()
    fig2.savefig("Ore_Level_Plot.png")
