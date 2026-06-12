from drs.module import drs
from drs.telemetry import Telemetry

from .config import BaseDualStockpileConfig, ConcentratorConfig, CyanidationConfig
from .stockpiles import Stockpile
from .supply_chain import (
    BaseMineFace, BaseFleetLogistics, BaseMetallurgicalPlant,
    ConcentratorMineFace, ConcentratorFleet, ConcentratorPlant,
    CyanidationMineFace, CyanidationFleet, CyanidationPlant
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
    def __init__(self, config: BaseDualStockpileConfig, enable_telemetry: bool = False):
        super().__init__()
        self.config = config
        self.enable_telemetry = enable_telemetry

        self.generator = None
        self.mine: BaseMineFace = None
        self.fleet: BaseFleetLogistics = None
        self.plant: BaseMetallurgicalPlant = None
        self.controller: BaseBlendingController = None

        self.global_time = drs.Timer("GlobalTime_Timer", initial_value=0.0)

    def setup_telemetry(self):
        if self.enable_telemetry:
            self.telemetry = Telemetry(self)
            self.register_post_step_hook(self.telemetry.snapshot)

            self.telemetry.register_metric(
                "MassOfCurrentParcel_State",
                lambda t, m, s, h: m.mine.true_current_parcel_mass.value,
            )
            self.telemetry.register_metric(
                "CurrentParcelRoutingFraction_State",
                lambda t, m, s, h: m.fleet.fraction_to_ore2.value,
            )
            self.telemetry.register_metric(
                "Campaign_Shutdown_Timer",
                lambda t, m, s, h: m.controller.time_executed_campaign_shutdown.value,
            )
            self.telemetry.register_metric(
                "Contingency_Timer",
                lambda t, m, s, h: m.controller.time_executed_contingency.value,
            )

            if hasattr(self.plant, "true_current_mill_kpt"):
                self.telemetry.register_metric(
                    "CurrentMillKPT_State",
                    lambda t, m, s, h: m.plant.true_current_mill_kpt.value,
                )

            if hasattr(self.plant, "true_total_cyanide_consumed"):
                self.telemetry.register_metric(
                    "TotalCyanideConsumed_Level",
                    lambda t, m, s, h: m.plant.true_total_cyanide_consumed.value,
                )

    def forward(self):
        self.global_time.rate = 1.0

        self.controller()

        mine_flow = self.mine()
        ore1_flow, ore2_flow = self.fleet(mine_flow)

        out1 = self.true_ore1_stock(self.controller.target_ore1_mill_rate.value, inflow=ore1_flow)
        out2 = self.true_ore2_stock(self.controller.target_ore2_mill_rate.value, inflow=ore2_flow)

        self.plant(out1, out2)

    def is_terminating_condition_met(self) -> bool:
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
    def __init__(self, config: ConcentratorConfig, enable_telemetry: bool = False):
        super().__init__(config, enable_telemetry)

        self.generator = StochasticFaciesGradeGenerator(self.config)
        self.mine = ConcentratorMineFace(self.config, self.generator)
        self.fleet = ConcentratorFleet(self.config)

        initial_fraction = self.config.mean_grade / self.config.grade_percentage_scale
        initial_mass1 = (1 - initial_fraction) * self.config.target_ore_stock_level
        self.true_ore1_stock = Stockpile(
            name="TrueOre1Stock",
            expected_attributes=["grade"],
            initial_mass=initial_mass1,
            initial_attributes={"grade": initial_mass1 * self.config.mean_grade},
        )
        initial_mass2 = initial_fraction * self.config.target_ore_stock_level
        self.true_ore2_stock = Stockpile(
            name="TrueOre2Stock",
            expected_attributes=["grade"],
            initial_mass=initial_mass2,
            initial_attributes={"grade": initial_mass2 * self.config.mean_grade},
        )

        self.plant = ConcentratorPlant(self.config, self.mine, self.fleet, self.true_ore1_stock, self.true_ore2_stock)
        self.controller = ConcentratorController(self.config, self.mine, self.fleet, self.plant)

        self.setup_telemetry()

class CyanidationModel(BaseBlendingModel):
    def __init__(self, config: CyanidationConfig, enable_telemetry: bool = False):
        super().__init__(config, enable_telemetry)

        self.generator = CyanideGeostatisticalBlockGenerator(self.config)
        self.mine = CyanidationMineFace(self.config, self.generator)
        self.fleet = CyanidationFleet(self.config)

        initial_ore2_fraction = 0.70
        initial_mass1 = (1 - initial_ore2_fraction) * self.config.target_ore_stock_level
        self.true_ore1_stock = Stockpile(
            name="TrueOre1Stock",
            expected_attributes=["cyanide"],
            initial_mass=initial_mass1,
            initial_attributes={
                "cyanide": initial_mass1 * self.config.mean_cyanide_consumption
            },
        )
        initial_mass2 = initial_ore2_fraction * self.config.target_ore_stock_level
        self.true_ore2_stock = Stockpile(
            name="TrueOre2Stock",
            expected_attributes=["cyanide"],
            initial_mass=initial_mass2,
            initial_attributes={
                "cyanide": initial_mass2 * self.config.mean_cyanide_consumption
            },
        )

        self.plant = CyanidationPlant(self.config, self.mine, self.fleet, self.true_ore1_stock, self.true_ore2_stock)
        self.controller = CyanidationController(self.config, self.mine, self.fleet, self.plant)

        self.setup_telemetry()


