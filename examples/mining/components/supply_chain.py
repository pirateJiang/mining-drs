from typing import Tuple
from drs.module import drs
from drs.flow import Flow
from .data import MineOutput
from .modes import OperatingMode
from .config import ConcentratorConfig

# ---------------------------------------------------------
# MINE FACE
# ---------------------------------------------------------


class BaseMineFace(drs.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config

        self.active_parcel_initial_mass = drs.Variable("active_parcel_initial_mass", 0.0)

        self.cumulative_extracted_mass = drs.Level(
            "cumulative_extracted_mass", initial_value=0.0
        )
        self.parcel_extracted_mass = drs.Level(
            "parcel_extracted_mass", initial_value=0.0
        )

    def _load_next_batch(self):
        raise NotImplementedError("Subclasses must define how to parse the DataPoint.")

    def _get_current_attr_value(self) -> float:
        raise NotImplementedError("Subclasses must define current ore attribute value.")

    def forward(self):
        target_extraction_rate = self.parent.controller.target_mine_mass_rate.value

        if (
            self.parcel_extracted_mass.value
            >= self.active_parcel_initial_mass.value - 1e-6
        ):
            self._load_next_batch()
            self.parcel_extracted_mass.value = 0.0
            self.parcel_extracted_mass.upper_threshold = (
                self.active_parcel_initial_mass.value
            )

        if (
            self.cumulative_extracted_mass.value
            < self.config.ore_to_be_extracted_during_warming_period
        ):
            self.cumulative_extracted_mass.upper_threshold = (
                self.config.ore_to_be_extracted_during_warming_period
            )
        else:
            self.cumulative_extracted_mass.upper_threshold = self.config.total_ore_to_extract

        self.parcel_extracted_mass.upper_threshold = (
            self.active_parcel_initial_mass.value
        )

        self.cumulative_extracted_mass.rate = target_extraction_rate
        self.parcel_extracted_mass.rate = target_extraction_rate
        return Flow(value=MineOutput(
            extraction_rate=target_extraction_rate,
            parcel_mass=self.active_parcel_initial_mass.value,
            attr_value=self._get_current_attr_value(),
        ))


class ConcentratorMineFace(BaseMineFace):
    def __init__(self, config: ConcentratorConfig):
        super().__init__(config)
        from .generators import StochasticFaciesGradeGenerator
        self.generator = StochasticFaciesGradeGenerator(self.config)
        self.active_parcel_grade = drs.Variable("active_parcel_grade", 0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel_flow = self.generator()
            parcel = parcel_flow.value
            self.active_parcel_initial_mass.value = parcel.mass
            self.active_parcel_grade.value = parcel.grade
        except StopIteration:
            pass

    def _get_current_attr_value(self) -> float:
        return self.active_parcel_grade.value

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
        self.stockpile2_routing_fraction = drs.Variable("stockpile2_routing_fraction", 0.0)

    def calculate_routing_fraction(self, incoming_attr_value: float) -> float:
        raise NotImplementedError(
            "Subclasses must define how routing fraction is calculated."
        )

    def forward(self, mine_flow: Flow = None) -> Tuple[Flow, Flow]:
        if mine_flow is not None:
            incoming = mine_flow.value
            self.stockpile2_routing_fraction.value = self.calculate_routing_fraction(incoming.attr_value)
            f = self.stockpile2_routing_fraction.value
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
            self.stockpile2_routing_fraction.value = 0.0
            return Flow(value=MineOutput(0, 0, 0)), Flow(value=MineOutput(0, 0, 0))


class ConcentratorFleet(BaseFleetLogistics):
    def __init__(self, config):
        super().__init__(config, expected_attributes=["contained_grade_mass"])

    def calculate_routing_fraction(self, attr_value: float) -> float:
        return attr_value / self.config.grade_percentage_scale





# ---------------------------------------------------------
# METALLURGICAL PLANT
# ---------------------------------------------------------


class BaseMetallurgicalPlant(drs.Module):
    def __init__(self, config, mine, fleet: BaseFleetLogistics, ore1_stock, ore2_stock):
        super().__init__()
        self.config = config
        self.mine = mine
        self.fleet = fleet

        self.cumulative_milled_mass = drs.Level(
            "cumulative_milled_mass", initial_value=0.0
        )

        self._ore1_stock = ore1_stock
        self._ore2_stock = ore2_stock

    def forward(self, ore1_outflow, ore2_outflow):
        o1 = ore1_outflow.value if isinstance(ore1_outflow, Flow) else ore1_outflow
        o2 = ore2_outflow.value if isinstance(ore2_outflow, Flow) else ore2_outflow
        
        total_inflow = o1 + o2
        self.cumulative_milled_mass.rate = total_inflow
        



class ConcentratorPlant(BaseMetallurgicalPlant):
    def __init__(self, config: ConcentratorConfig, mine, fleet: BaseFleetLogistics, ore1_stock, ore2_stock):
        super().__init__(config, mine, fleet, ore1_stock, ore2_stock)

    def forward(self, ore1_outflow, ore2_outflow):
        super().forward(ore1_outflow, ore2_outflow)



