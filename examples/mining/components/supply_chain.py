from drs.module import drs
from drs.data import BaseOreGenerator, MaterialFlow
from .config import ConcentratorConfig, CyanidationConfig

# ---------------------------------------------------------
# MINE FACE
# ---------------------------------------------------------

class BaseMineFace(drs.Module):
    def __init__(self, config, loader: BaseOreGenerator):
        super().__init__()
        self.config = config
        self.loader = iter(loader)

        self.true_current_parcel_mass = drs.State("true_parcel_mass", 0.0)

        self.true_ore_extraction = drs.Level("TrueOreExtraction_Level", initial_value=0.0)
        self.true_ore_extracted_from_current_parcel = drs.Level("TrueOreExtractedFromCurrentParcel_Level", initial_value=0.0)

    def _load_next_batch(self):
        raise NotImplementedError("Subclasses must define how to parse the OreParcel.")
        
    @property
    def outgoing_flow(self) -> MaterialFlow:
        """Constructs and returns the continuous flow spawned from the discrete block model."""
        raise NotImplementedError("Subclasses must define how to construct the outgoing flow.")

    def check_transitions(self, trigger_var: drs.Variable = None, is_upper: bool = True):
        if trigger_var == self.true_ore_extracted_from_current_parcel and is_upper:
            self._load_next_batch()
            self.true_ore_extracted_from_current_parcel.value = 0.0
            self.true_ore_extracted_from_current_parcel.upper_threshold = self.true_current_parcel_mass.value

    def update_rates(self):
        if (self.true_ore_extraction.value < self.config.ore_to_be_extracted_during_warming_period):
            self.true_ore_extraction.upper_threshold = self.config.ore_to_be_extracted_during_warming_period
        else:
            self.true_ore_extraction.upper_threshold = self.config.total_ore_to_extract

        self.true_ore_extracted_from_current_parcel.upper_threshold = self.true_current_parcel_mass.value


class ConcentratorMineFace(BaseMineFace):
    def __init__(self, config: ConcentratorConfig, loader: BaseOreGenerator):
        super().__init__(config, loader)
        self.true_current_parcel_grade = drs.State("true_parcel_grade", 0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel = next(self.loader)
            self.true_current_parcel_mass.value = parcel.mass
            self.true_current_parcel_grade.value = parcel.grade
        except StopIteration:
            pass

    @property
    def outgoing_flow(self) -> MaterialFlow:
        r = self.true_ore_extraction.rate
        grade = self.true_current_parcel_grade.value
        return MaterialFlow(mass_rate=r, attributes={"grade": r * grade})


class CyanidationMineFace(BaseMineFace):
    def __init__(self, config: CyanidationConfig, loader: BaseOreGenerator):
        super().__init__(config, loader)
        self.true_current_parcel_cyanide = drs.State("true_parcel_cyanide", 0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel = next(self.loader)
            self.true_current_parcel_mass.value = parcel.mass
            self.true_current_parcel_cyanide.value = getattr(parcel, "cyanide_kpt", getattr(parcel, "grade", 0.0))
        except StopIteration:
            pass
            
    @property
    def outgoing_flow(self) -> MaterialFlow:
        r = self.true_ore_extraction.rate
        cyanide = self.true_current_parcel_cyanide.value
        return MaterialFlow(mass_rate=r, attributes={"cyanide": r * cyanide})



# ---------------------------------------------------------
# FLEET LOGISTICS
# ---------------------------------------------------------
from drs.network import Node

class BaseFleetLogistics(Node):
    def __init__(self, config, mine, expected_attributes: list):
        # Now a formal Network Node
        super().__init__("Fleet", attributes=["mass"] + expected_attributes)
        self.config = config
        self.mine = mine
        self.fraction_to_ore2 = 0.0  # Set dynamically by controller/modes

    def resolve_outgoing_flow(self):
        """The Network orchestrates this. Splits accumulated flow between Ore 1 and Ore 2."""
        if len(self.out_edges) != 2:
            return

        # Safely aggregate all incoming physical flows provided by the Network
        total_inflows = {}
        for edge in self.in_edges:
            for attr, rate in edge.flow_rates.items():
                total_inflows[attr] = total_inflows.get(attr, 0.0) + rate

        # Perform the split
        rates_to_ore1 = {k: v * (1.0 - self.fraction_to_ore2) for k, v in total_inflows.items()}
        rates_to_ore2 = {k: v * self.fraction_to_ore2 for k, v in total_inflows.items()}

        # out_edges[0] points to Ore 1, out_edges[1] points to Ore 2
        self.out_edges[0].set_rates(rates_to_ore1)
        self.out_edges[1].set_rates(rates_to_ore2)
        
    def update_rates(self):
        pass # Remove legacy pass-through logic; the Network resolves this automatically.


class ConcentratorFleet(BaseFleetLogistics):
    def __init__(self, config, mine):
        super().__init__(config, mine, expected_attributes=["grade"])


class CyanidationFleet(BaseFleetLogistics):
    def __init__(self, config, mine):
        super().__init__(config, mine, expected_attributes=["cyanide"])


# ---------------------------------------------------------
# METALLURGICAL PLANT
# ---------------------------------------------------------

class BaseMetallurgicalPlant(drs.Module):
    def __init__(self, config, fleet: BaseFleetLogistics):
        super().__init__()
        self.config = config
        self.fleet = fleet

        self.true_ore_stock = drs.Level("TrueOreStock_Level", initial_value=self.config.target_ore_stock_level)
        
        self.true_total_ore_milled = drs.Level("TrueTotalOreMilled_Level", initial_value=0.0)

        # To be initialized by subclass based on fractions
        self.true_ore1_stock = None
        self.true_ore2_stock = None

    def update_rates(self):
        pass


from .stockpiles import Stockpile

class ConcentratorPlant(BaseMetallurgicalPlant):
    def __init__(self, config: ConcentratorConfig, fleet: BaseFleetLogistics):
        super().__init__(config, fleet)
        
        initial_fraction = self.config.mean_grade / self.config.grade_percentage_scale

        initial_mass1 = (1 - initial_fraction) * self.config.target_ore_stock_level
        self.true_ore1_stock = Stockpile(
            name="TrueOre1Stock",
            expected_attributes=["grade"],
            initial_mass=initial_mass1,
            initial_attributes={"grade": initial_mass1 * self.config.mean_grade}
        )
        
        initial_mass2 = initial_fraction * self.config.target_ore_stock_level
        self.true_ore2_stock = Stockpile(
            name="TrueOre2Stock",
            expected_attributes=["grade"],
            initial_mass=initial_mass2,
            initial_attributes={"grade": initial_mass2 * self.config.mean_grade}
        )

    def update_rates(self):
        super().update_rates()


class CyanidationPlant(BaseMetallurgicalPlant):
    def __init__(self, config: CyanidationConfig, fleet: BaseFleetLogistics):
        super().__init__(config, fleet)
        
        initial_ore2_fraction = 0.70

        initial_mass1 = (1 - initial_ore2_fraction) * self.config.target_ore_stock_level
        self.true_ore1_stock = Stockpile(
            name="TrueOre1Stock",
            expected_attributes=["cyanide"],
            initial_mass=initial_mass1,
            initial_attributes={"cyanide": initial_mass1 * self.config.mean_cyanide_consumption}
        )
        
        initial_mass2 = initial_ore2_fraction * self.config.target_ore_stock_level
        self.true_ore2_stock = Stockpile(
            name="TrueOre2Stock",
            expected_attributes=["cyanide"],
            initial_mass=initial_mass2,
            initial_attributes={"cyanide": initial_mass2 * self.config.mean_cyanide_consumption}
        )

        self.true_total_cyanide_consumed = drs.Level("TrueTotalCyanideConsumed_Level", initial_value=0.0)
        self.true_current_mill_kpt = drs.State("true_current_mill_kpt", 0.0)

    def check_transitions(self, trigger_var: drs.Variable = None, is_upper: bool = True):
        # We need to reach back to the mine for ore_extraction logic since it was moved!
        if trigger_var == self.fleet.mine.true_ore_extraction and is_upper:
            if abs(self.fleet.mine.true_ore_extraction.value - self.config.ore_to_be_extracted_during_warming_period) < 0.1:
                self.true_total_cyanide_consumed.value = 0.0
                self.true_total_ore_milled.value = 0.0

    def update_rates(self):
        super().update_rates()
        if self.true_total_ore_milled.rate > 0:
            self.true_current_mill_kpt.value = self.true_total_cyanide_consumed.rate / self.true_total_ore_milled.rate
        else:
            self.true_current_mill_kpt.value = 0.0

