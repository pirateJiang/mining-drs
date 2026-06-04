from drs.module import drs
from drs.telemetry import Telemetry

from .config import BaseDualStockpileConfig, ConcentratorConfig, CyanidationConfig
from .plants import BaseBlendingPlant, ConcentratorPlant, CyanidationPlant
from .controllers import (
    BaseBlendingController,
    ConcentratorController,
    CyanidationController,
)
from .generators import (
    StochasticFaciesGradeGenerator,
    CyanideGeostatisticalBlockGenerator,
)


class BaseBlendingModel(drs.Module):
    """
    Abstract base model that wires together a Generator, Plant, and Controller.
    Handles global simulation updates, transitions, and telemetry.
    """

    def __init__(self, config: BaseDualStockpileConfig, enable_telemetry: bool = False):
        super().__init__()
        self.config = config
        self.enable_telemetry = enable_telemetry

        # These must be instantiated by subclasses!
        self.generator = None
        self.plant: BaseBlendingPlant = None
        self.controller: BaseBlendingController = None
        
        # Track global simulation time
        self.global_time = drs.Timer("GlobalTime_Timer", initial_value=0.0)

    def setup_telemetry(self):
        """Called by subclasses after components are instantiated."""
        if self.enable_telemetry:
            self.telemetry = Telemetry(self)
            self.register_post_step_hook(self.telemetry.snapshot)

            self.telemetry.register_metric(
                "MassOfCurrentParcel_State",
                lambda t, m, s, h: m.plant.current_parcel_mass.value,
            )
            # Use the universal routing fraction instead of hardcoding 'grade' or 'cyanide'
            self.telemetry.register_metric(
                "CurrentParcelRoutingFraction_State",
                lambda t, m, s, h: m.plant.current_parcel_routing_fraction,
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
        self.global_time.rate = 1.0
        self.plant.update_rates()
        self.controller.update_rates()

    def is_terminating_condition_met(self) -> bool:
        # Terminate when the mine has extracted all its ore reserves
        return self.plant.ore_extraction.value >= self.config.total_ore_to_extract

    def check_transitions(
        self, trigger_var: drs.Variable = None, is_upper: bool = True
    ):
        self.plant.check_transitions(trigger_var, is_upper)
        self.controller.check_transitions(trigger_var, is_upper)

    def is_terminating_condition_met(self) -> bool:
        c = self.config
        extraction_met = self.plant.ore_extraction.value >= c.total_ore_to_extract
        stock_met = abs(self.plant.ore_stock.value - c.target_ore_stock_level) < 0.001

        return extraction_met and stock_met

    def print_statistics(self):
        print("\n--- Output Statistics ---")
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

        active_time = total_time - self.controller.time_shutdown.value
        if active_time > 0:
            throughput = (
                self.plant.ore_extraction.value
                - self.config.ore_to_be_extracted_during_warming_period
            ) / active_time
            print(f"Throughput: {throughput:.4f} tons/day")
        else:
            print("Active time is 0. Cannot calculate throughput.")


class ConcentratorModel(BaseBlendingModel):
    """
    Assembles the 2019 Navarra Concentrator simulation using statistical grade generation.
    """

    def __init__(self, config: ConcentratorConfig, enable_telemetry: bool = False):
        super().__init__(config, enable_telemetry)

        # Assemble specific components
        self.generator = StochasticFaciesGradeGenerator(self.config)
        self.plant = ConcentratorPlant(self.config, self.generator)
        self.controller = ConcentratorController(self.config, self.plant)

        self.setup_telemetry()


class CyanidationModel(BaseBlendingModel):
    """
    Assembles the 2026/2023 Órdenes Cyanidation simulation using SGS block modeling.
    """

    def __init__(self, config: CyanidationConfig, enable_telemetry: bool = False):
        super().__init__(config, enable_telemetry)

        # Assemble specific components
        self.generator = CyanideGeostatisticalBlockGenerator(self.config)
        self.plant = CyanidationPlant(self.config, self.generator)
        self.controller = CyanidationController(self.config, self.plant)

        self.setup_telemetry()
