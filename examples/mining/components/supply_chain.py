from drs.module import drs
from drs.data import BaseOreGenerator
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



# ---------------------------------------------------------
# FLEET LOGISTICS
# ---------------------------------------------------------

class BaseFleetLogistics(drs.Module):
    def __init__(self, config, mine: BaseMineFace):
        super().__init__()
        self.config = config
        self.mine = mine
        # Pass-through rate
        self.true_transit_rate = 0.0



    def update_rates(self):
        # Perfect pass-through for now
        self.true_transit_rate = self.mine.true_ore_extraction.rate


class ConcentratorFleet(BaseFleetLogistics):
    pass


class CyanidationFleet(BaseFleetLogistics):
    pass


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


class ConcentratorPlant(BaseMetallurgicalPlant):
    def __init__(self, config: ConcentratorConfig, fleet: BaseFleetLogistics):
        super().__init__(config, fleet)
        
        initial_fraction = self.config.mean_grade / self.config.grade_percentage_scale

        self.true_ore1_stock = drs.Level("TrueOre1Stock_Level", initial_value=(1 - initial_fraction) * self.config.target_ore_stock_level)
        self.true_ore2_stock = drs.Level("TrueOre2Stock_Level", initial_value=initial_fraction * self.config.target_ore_stock_level)

    def update_rates(self):
        super().update_rates()


class CyanidationPlant(BaseMetallurgicalPlant):
    def __init__(self, config: CyanidationConfig, fleet: BaseFleetLogistics):
        super().__init__(config, fleet)
        
        initial_ore2_fraction = 0.70

        self.true_ore1_stock = drs.Level("TrueOre1Stock_Level", initial_value=(1 - initial_ore2_fraction) * self.config.target_ore_stock_level)
        self.true_ore2_stock = drs.Level("TrueOre2Stock_Level", initial_value=initial_ore2_fraction * self.config.target_ore_stock_level)

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

