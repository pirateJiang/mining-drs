from drs.module import drs
from drs.telemetry import Telemetry

from .config import BaseDualStockpileConfig, ConcentratorConfig
from .stockpiles import Stockpile
from .supply_chain import (
    BaseMineFace, BaseFleetLogistics, BaseMetallurgicalPlant,
    ConcentratorMineFace, ConcentratorFleet, ConcentratorPlant
)
from .controllers import (
    BaseBlendingController,
    ConcentratorController,
)
from .generators import (
    StochasticFaciesGradeGenerator,
)


class BaseBlendingModel(drs.Module):
    def __init__(self, config: BaseDualStockpileConfig, enable_telemetry: bool = False):
        super().__init__()
        self.config = config
        self.enable_telemetry = enable_telemetry

        self.generator = None
        self.mine: BaseMineFace = None
        self.fleet: BaseFleetLogistics = None
        self.plant: BaseMetallurgicalPlant = None
        self.controller: BaseBlendingController = None

        self.global_time = drs.Timer("GlobalTime", initial_value=0.0)

    def setup_telemetry(self):
        if self.enable_telemetry:
            self.telemetry = Telemetry(self)
            self.register_post_step_hook(self.telemetry.snapshot)

            self.telemetry.register_metric(
                "MassOfCurrentParcel",
                lambda t, m, s, h: m.mine.active_parcel_initial_mass.value,
            )
            self.telemetry.register_metric(
                "CurrentParcelRoutingFraction",
                lambda t, m, s, h: m.fleet.stockpile2_routing_fraction.value,
            )
            self.telemetry.register_metric(
                "Campaign_Shutdown",
                lambda t, m, s, h: m.controller.current_campaign_duration.value,
            )
            self.telemetry.register_metric(
                "Contingency",
                lambda t, m, s, h: m.controller.current_contingency_duration.value,
            )



    def forward(self):
        self.global_time.rate = 1.0

        self.controller()

        mine_flow = self.mine()
        ore1_flow, ore2_flow = self.fleet(mine_flow)

        out1 = self.ore1_stock(self.controller.target_stock1_outflow_rate, inflow=ore1_flow)
        out2 = self.ore2_stock(self.controller.target_stock2_outflow_rate, inflow=ore2_flow)

        self.plant(out1, out2)

    def is_terminating_condition_met(self) -> bool:
        return self.mine.cumulative_extracted_mass.value >= self.config.total_ore_to_extract

    def print_statistics(self):
        print("\n--- Output Statistics ---")
        total_time = (
            self.controller.cumulative_time_mode_a.value
            + self.controller.cumulative_time_mode_a_contingency.value
            + self.controller.cumulative_time_mode_a_surging.value
            + self.controller.cumulative_time_mode_b.value
            + self.controller.cumulative_time_mode_b_contingency.value
            + self.controller.cumulative_time_mode_b_surging.value
            + self.controller.cumulative_time_shutdown.value
        )

        if total_time > 0:
            print(
                f"PortionOfTimeInModeA: {self.controller.cumulative_time_mode_a.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeAContingency: {self.controller.cumulative_time_mode_a_contingency.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeAMineSurging: {self.controller.cumulative_time_mode_a_surging.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeB: {self.controller.cumulative_time_mode_b.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeBContingency: {self.controller.cumulative_time_mode_b_contingency.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInModeBMineSurging: {self.controller.cumulative_time_mode_b_surging.value / total_time:.4f}"
            )
            print(
                f"PortionOfTimeInShutdown: {self.controller.cumulative_time_shutdown.value / total_time:.4f}"
            )
        else:
            print("Total time is 0. Cannot calculate mode portions.")

        active_time = total_time - self.controller.cumulative_time_shutdown.value
        if active_time > 0:
            if hasattr(self.plant, "cumulative_milled_mass"):
                total_ore_processed = self.plant.cumulative_milled_mass.value
            else:
                total_ore_processed = self.mine.cumulative_extracted_mass.value - self.config.ore_to_be_extracted_during_warming_period

            throughput = total_ore_processed / active_time
            print(f"Throughput: {throughput:.4f} tons/day")
        else:
            print("Active time is 0. Cannot calculate throughput.")


class ConcentratorModel(BaseBlendingModel):
    def __init__(self, config: ConcentratorConfig, enable_telemetry: bool = False):
        super().__init__(config, enable_telemetry)

        self.mine = ConcentratorMineFace(self.config)
        self.fleet = ConcentratorFleet(self.config)

        initial_fraction = self.config.mean_grade / self.config.grade_percentage_scale
        initial_mass1 = (1 - initial_fraction) * self.config.target_ore_stock_level
        self.ore1_stock = Stockpile(
            name="Ore1Stock",
            expected_attributes=["contained_grade_mass"],
            initial_mass=initial_mass1,
            initial_attributes={"contained_grade_mass": initial_mass1 * self.config.mean_grade},
        )
        initial_mass2 = initial_fraction * self.config.target_ore_stock_level
        self.ore2_stock = Stockpile(
            name="Ore2Stock",
            expected_attributes=["contained_grade_mass"],
            initial_mass=initial_mass2,
            initial_attributes={"contained_grade_mass": initial_mass2 * self.config.mean_grade},
        )

        self.plant = ConcentratorPlant(self.config, self.mine, self.fleet, self.ore1_stock, self.ore2_stock)
        self.controller = ConcentratorController(self.config, self.mine, self.fleet, self.plant)

        self.setup_telemetry()

