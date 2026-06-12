from typing import Tuple
from drs.module import drs
from drs.flow import Flow
from .data import MineOutput
from .modes import OperatingMode
from .config import ConcentratorConfig, CyanidationConfig

# ---------------------------------------------------------
# MINE FACE
# ---------------------------------------------------------


class BaseMineFace(drs.Module):
    def __init__(self, config, loader: drs.DataSource):
        super().__init__()
        self.config = config
        self.loader = loader

        self.true_current_parcel_mass = drs.Variable("true_parcel_mass", 0.0)

        self.true_ore_extraction = drs.Level(
            "TrueOreExtraction_Level", initial_value=0.0
        )
        self.true_ore_extracted_from_current_parcel = drs.Level(
            "TrueOreExtractedFromCurrentParcel_Level", initial_value=0.0
        )

    def _load_next_batch(self):
        raise NotImplementedError("Subclasses must define how to parse the DataPoint.")

    def _get_current_attr_value(self) -> float:
        raise NotImplementedError("Subclasses must define current ore attribute value.")

    def forward(self):
        target_extraction_rate = self.parent.controller.target_extraction_rate.value

        if (
            self.true_ore_extracted_from_current_parcel.value
            >= self.true_current_parcel_mass.value - 1e-6
        ):
            self._load_next_batch()
            self.true_ore_extracted_from_current_parcel.value = 0.0
            self.true_ore_extracted_from_current_parcel.upper_threshold = (
                self.true_current_parcel_mass.value
            )

        if (
            self.true_ore_extraction.value
            < self.config.ore_to_be_extracted_during_warming_period
        ):
            self.true_ore_extraction.upper_threshold = (
                self.config.ore_to_be_extracted_during_warming_period
            )
        else:
            self.true_ore_extraction.upper_threshold = self.config.total_ore_to_extract

        self.true_ore_extracted_from_current_parcel.upper_threshold = (
            self.true_current_parcel_mass.value
        )

        self.true_ore_extraction.rate = target_extraction_rate
        self.true_ore_extracted_from_current_parcel.rate = target_extraction_rate
        return Flow(value=MineOutput(
            extraction_rate=target_extraction_rate,
            parcel_mass=self.true_current_parcel_mass.value,
            attr_value=self._get_current_attr_value(),
        ))


class ConcentratorMineFace(BaseMineFace):
    def __init__(self, config: ConcentratorConfig, loader: drs.DataSource):
        super().__init__(config, loader)
        self.true_current_parcel_grade = drs.Variable("true_parcel_grade", 0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel_flow = self.loader()
            parcel = parcel_flow.value
            self.true_current_parcel_mass.value = parcel.mass
            self.true_current_parcel_grade.value = parcel.grade
        except StopIteration:
            pass

    def _get_current_attr_value(self) -> float:
        return self.true_current_parcel_grade.value

    def forward(self):
        return super().forward()


class CyanidationMineFace(BaseMineFace):
    def __init__(self, config: CyanidationConfig, loader: drs.DataSource):
        super().__init__(config, loader)
        self.true_current_parcel_cyanide = drs.Variable("true_parcel_cyanide", 0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel_flow = self.loader()
            parcel = parcel_flow.value
            self.true_current_parcel_mass.value = parcel.mass
            self.true_current_parcel_cyanide.value = getattr(
                parcel, "cyanide_kpt", getattr(parcel, "grade", 0.0)
            )
        except StopIteration:
            pass

    def _get_current_attr_value(self) -> float:
        return self.true_current_parcel_cyanide.value

    def forward(self):
        return super().forward()


# ---------------------------------------------------------
# FLEET LOGISTICS
# ---------------------------------------------------------


class BaseFleetLogistics(drs.Module):
    def __init__(self, config, expected_attributes: list):
        super().__init__()
        self.name = "Fleet"
        self.config = config
        self.expected_attributes = expected_attributes
        self.fraction_to_ore2 = drs.Variable("fraction_to_ore2", 0.0)

    def calculate_routing_fraction(self, incoming_attr_value: float) -> float:
        raise NotImplementedError(
            "Subclasses must define how routing fraction is calculated."
        )

    def forward(self, mine_flow: Flow = None) -> Tuple[Flow, Flow]:
        if mine_flow is not None:
            incoming = mine_flow.value
            self.fraction_to_ore2.value = self.calculate_routing_fraction(incoming.attr_value)
            f = self.fraction_to_ore2.value
            payload1 = MineOutput(
                extraction_rate=incoming.extraction_rate * (1.0 - f),
                parcel_mass=incoming.parcel_mass,
                attr_value=incoming.attr_value,
            )
            payload2 = MineOutput(
                extraction_rate=incoming.extraction_rate * f,
                parcel_mass=incoming.parcel_mass,
                attr_value=incoming.attr_value,
            )
            return Flow(value=payload1), Flow(value=payload2)
        else:
            self.fraction_to_ore2.value = 0.0
            return Flow(value=MineOutput(0, 0, 0)), Flow(value=MineOutput(0, 0, 0))


class ConcentratorFleet(BaseFleetLogistics):
    def __init__(self, config):
        super().__init__(config, expected_attributes=["grade"])

    def calculate_routing_fraction(self, attr_value: float) -> float:
        return attr_value / self.config.grade_percentage_scale


class CyanidationFleet(BaseFleetLogistics):
    def __init__(self, config):
        super().__init__(config, expected_attributes=["cyanide"])

    def calculate_routing_fraction(self, attr_value: float) -> float:
        oxide_sulphide_threshold = 2.41
        if attr_value >= oxide_sulphide_threshold:
            return 0.001
        else:
            return 0.999


# ---------------------------------------------------------
# METALLURGICAL PLANT
# ---------------------------------------------------------


class BaseMetallurgicalPlant(drs.Module):
    def __init__(self, config, mine, fleet: BaseFleetLogistics, ore1_stock, ore2_stock):
        super().__init__()
        self.config = config
        self.mine = mine
        self.fleet = fleet

        self.true_ore_stock = drs.Level(
            "TrueOreStock_Level", initial_value=self.config.target_ore_stock_level
        )

        self.true_total_ore_milled = drs.Level(
            "TrueTotalOreMilled_Level", initial_value=0.0
        )

        self._ore1_stock = ore1_stock
        self._ore2_stock = ore2_stock

    def forward(self, ore1_outflow, ore2_outflow):
        o1 = ore1_outflow.value if isinstance(ore1_outflow, Flow) else ore1_outflow
        o2 = ore2_outflow.value if isinstance(ore2_outflow, Flow) else ore2_outflow
        
        total_inflow = o1 + o2
        self.true_total_ore_milled.rate = total_inflow
        
        extraction_rate = self.mine.true_ore_extraction.rate
        self.true_ore_stock.rate = extraction_rate - total_inflow

        if self.true_ore_stock.rate < 0:
            self.true_ore_stock.lower_threshold = 0.0


class ConcentratorPlant(BaseMetallurgicalPlant):
    def __init__(self, config: ConcentratorConfig, mine, fleet: BaseFleetLogistics, ore1_stock, ore2_stock):
        super().__init__(config, mine, fleet, ore1_stock, ore2_stock)

    def forward(self, ore1_outflow, ore2_outflow):
        super().forward(ore1_outflow, ore2_outflow)


class CyanidationPlant(BaseMetallurgicalPlant):
    def __init__(self, config: CyanidationConfig, mine, fleet: BaseFleetLogistics, ore1_stock, ore2_stock):
        super().__init__(config, mine, fleet, ore1_stock, ore2_stock)

        self.true_total_cyanide_consumed = drs.Level(
            "TrueTotalCyanideConsumed_Level", initial_value=0.0
        )
        self.true_current_mill_kpt = drs.Variable("true_current_mill_kpt", 0.0)

    def forward(self, ore1_outflow, ore2_outflow):
        if (
            abs(
                self.mine.true_ore_extraction.value
                - self.config.ore_to_be_extracted_during_warming_period
            )
            < 1e-6
        ):
            self.true_total_cyanide_consumed.value = 0.0
            self.true_total_ore_milled.value = 0.0

        super().forward(ore1_outflow, ore2_outflow)

        o1 = ore1_outflow.value if isinstance(ore1_outflow, Flow) else ore1_outflow
        o2 = ore2_outflow.value if isinstance(ore2_outflow, Flow) else ore2_outflow
        s1, s2 = self._ore1_stock, self._ore2_stock
        ore1_cyanide = o1 * s1.current_concentration("cyanide")
        ore2_cyanide = o2 * s2.current_concentration("cyanide")
        cyanide_consumed = ore1_cyanide + ore2_cyanide
        self.true_total_cyanide_consumed.rate = cyanide_consumed

        if self.true_total_ore_milled.rate > 0:
            self.true_current_mill_kpt.value = (
                self.true_total_cyanide_consumed.rate / self.true_total_ore_milled.rate
            )
        else:
            self.true_current_mill_kpt.value = 0.0
