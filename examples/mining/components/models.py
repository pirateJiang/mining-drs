from drs.module import drs
from drs.telemetry import Telemetry

from .config import BaseDualStockpileConfig, ConcentratorConfig, CyanidationConfig
from .supply_chain import (
    BaseMineFace, BaseFleetLogistics, BaseMetallurgicalPlant,
    ConcentratorMineFace, ConcentratorFleet, ConcentratorPlant,
    CyanidationMineFace, CyanidationFleet, CyanidationPlant
)
from .sensors import (
    BaseSensorNetwork, ConcentratorSensorNetwork, CyanidationSensorNetwork
)
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
        self.mine: BaseMineFace = None
        self.fleet: BaseFleetLogistics = None
        self.plant: BaseMetallurgicalPlant = None
        self.sensors: BaseSensorNetwork = None
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
                lambda t, m, s, h: m.mine.true_current_parcel_mass.value,
            )
            # Use the universal routing fraction instead of hardcoding 'grade' or 'cyanide'
            self.telemetry.register_metric(
                "CurrentParcelRoutingFraction_State",
                lambda t, m, s, h: m.sensors.belief_routing_fraction,
            )
            self.telemetry.register_metric(
                "Campaign_Shutdown_Timer",
                lambda t, m, s, h: m.controller.time_executed_campaign_shutdown.value,
            )
            self.telemetry.register_metric(
                "Contingency_Timer",
                lambda t, m, s, h: m.controller.time_executed_contingency.value,
            )
            
            # Add dynamic tracking for stockpile attributes
            if hasattr(self.sensors, "belief_ore1_grade"):
                self.telemetry.register_metric(
                    "Belief_Ore1_Grade_State",
                    lambda t, m, s, h: m.sensors.belief_ore1_grade.value,
                )
                self.telemetry.register_metric(
                    "Belief_Ore2_Grade_State",
                    lambda t, m, s, h: m.sensors.belief_ore2_grade.value,
                )
            
            if hasattr(self.sensors, "belief_ore1_cyanide"):
                self.telemetry.register_metric(
                    "Belief_Ore1_Cyanide_State",
                    lambda t, m, s, h: m.sensors.belief_ore1_cyanide.value,
                )
                self.telemetry.register_metric(
                    "Belief_Ore2_Cyanide_State",
                    lambda t, m, s, h: m.sensors.belief_ore2_cyanide.value,
                )

    def _get_mine_attr_value(self) -> float:
        raise NotImplementedError("Subclasses must define which attribute the mine exposes.")

    def forward(self):
        self.global_time.rate = 1.0

        # 1. Logic & Commands (Reads state from previous tick)
        current_mode = self.controller()
        self.mine(current_mode)
        self.fleet()

        # 2. Physics & Flow — mine & fleet state drives stockpile inflow rates
        r = self.mine.true_ore_extraction.rate
        f = self.fleet.fraction_to_ore2.value
        attr_value = self._get_mine_attr_value()

        targets = current_mode.get_target_rates(self)
        requested_1 = targets.ore1_milling_rate
        requested_2 = targets.ore2_milling_rate

        s1, s2 = self.plant.true_ore1_stock, self.plant.true_ore2_stock
        s1.mass.rate = r * (1.0 - f)
        s2.mass.rate = r * f
        for attr in s1.expected_attributes:
            getattr(s1, attr).rate = r * (1.0 - f) * attr_value
            getattr(s2, attr).rate = r * f * attr_value

        s1(requested_1)
        s2(requested_2)

        # 3. Plant reads stockpile outflows
        self.plant()

        # 4. Observation (Sensors record the newly calculated rates)
        self.sensors()

    def is_terminating_condition_met(self) -> bool:
        # Terminate when the mine has extracted all its ore reserves
        return self.mine.true_ore_extraction.value >= self.config.total_ore_to_extract



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
            if hasattr(self.plant, "true_total_ore_milled"):
                total_ore_processed = self.plant.true_total_ore_milled.value
            else:
                total_ore_processed = self.mine.true_ore_extraction.value - self.config.ore_to_be_extracted_during_warming_period

            throughput = total_ore_processed / active_time
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
        self.mine = ConcentratorMineFace(self.config, self.generator)
        self.fleet = ConcentratorFleet(self.config, self.mine)
        self.plant = ConcentratorPlant(self.config, self.fleet)
        self.sensors = ConcentratorSensorNetwork(self.config, self.mine, self.fleet, self.plant)
        self.controller = ConcentratorController(self.config, self.sensors, self.mine, self.fleet, self.plant)

        self.setup_telemetry()

    def _get_mine_attr_value(self) -> float:
        return self.mine.true_current_parcel_grade.value


class CyanidationModel(BaseBlendingModel):
    """
    Assembles the 2026/2023 Órdenes Cyanidation simulation using SGS block modeling.
    """

    def __init__(self, config: CyanidationConfig, enable_telemetry: bool = False):
        super().__init__(config, enable_telemetry)

        # Assemble specific components
        self.generator = CyanideGeostatisticalBlockGenerator(self.config)
        self.mine = CyanidationMineFace(self.config, self.generator)
        self.fleet = CyanidationFleet(self.config, self.mine)
        self.plant = CyanidationPlant(self.config, self.fleet)
        self.sensors = CyanidationSensorNetwork(self.config, self.mine, self.fleet, self.plant)
        self.controller = CyanidationController(self.config, self.sensors, self.mine, self.fleet, self.plant)

        self.setup_telemetry()

    def _get_mine_attr_value(self) -> float:
        return self.mine.true_current_parcel_cyanide.value
