from drs.module import drs
from drs.data import BaseOreGenerator
from .config import ConcentratorConfig, CyanidationConfig

class BaseBlendingPlant(drs.Module):
    """
    Abstract base class for a processing plant that utilizes dual-stockpile blending 
    to stabilize feed variations.
    """
    def __init__(self, config, loader: BaseOreGenerator):
        super().__init__()
        self.config = config
        self.loader = iter(loader)

        self.current_parcel_mass = drs.State("parcel_mass", 0.0)
        
        # Shared Mass Balance Levels
        self.ore_extraction = drs.Level("OreExtraction_Level", initial_value=0.0)
        self.ore_extracted_from_current_parcel = drs.Level(
            "OreExtractedFromCurrentParcel_Level", initial_value=0.0
        )
        self.ore_stock = drs.Level(
            "OreStock_Level", initial_value=self.config.target_ore_stock_level
        )
        
        # Note: ore1_stock and ore2_stock initializations are deferred to the subclasses 
        # because the initial split logic depends on the specific plant's metric.
        self.ore1_stock = None
        self.ore2_stock = None

    @property
    def current_parcel_routing_fraction(self) -> float:
        """Returns the fraction [0.0 - 1.0] of the current parcel that should go to Ore 2."""
        raise NotImplementedError("Subclasses must define how to route the parcel mass.")

    def _load_next_batch(self):
        raise NotImplementedError("Subclasses must define how to parse the OreParcel.")

    def check_transitions(self, trigger_var: drs.Variable = None, is_upper: bool = True):
        if trigger_var == self.ore_extracted_from_current_parcel and is_upper:
            self._load_next_batch()
            self.ore_extracted_from_current_parcel.value = 0.0
            self.ore_extracted_from_current_parcel.upper_threshold = (
                self.current_parcel_mass.value
            )

    def update_rates(self):
        # Apply Global / Shared Rules for plant
        if (self.ore_extraction.value < self.config.ore_to_be_extracted_during_warming_period):
            self.ore_extraction.upper_threshold = self.config.ore_to_be_extracted_during_warming_period
        else:
            self.ore_extraction.upper_threshold = self.config.total_ore_to_extract

        self.ore_extracted_from_current_parcel.upper_threshold = self.current_parcel_mass.value


class ConcentratorPlant(BaseBlendingPlant):
    """
    Based on Navarra (2019). Models a base-metal flotation concentrator 
    where mass is routed based on ore grade/hardness percentages.
    """
    def __init__(self, config: ConcentratorConfig, loader: BaseOreGenerator):
        super().__init__(config, loader)
        self.current_parcel_grade = drs.State("parcel_grade", 0.0)

        # Initialize split using grade configuration
        initial_fraction = self.config.mean_grade / self.config.grade_percentage_scale
        
        self.ore1_stock = drs.Level("Ore1Stock_Level", 
            initial_value=(1 - initial_fraction) * self.config.target_ore_stock_level)
        self.ore2_stock = drs.Level("Ore2Stock_Level", 
            initial_value=initial_fraction * self.config.target_ore_stock_level)

        self._load_next_batch()

    @property
    def current_parcel_routing_fraction(self) -> float:
        """Routes mass based on the grade percentage."""
        return self.current_parcel_grade.value / self.config.grade_percentage_scale

    def _load_next_batch(self):
        try:
            parcel = next(self.loader)
            self.current_parcel_mass.value = parcel.mass
            self.current_parcel_grade.value = parcel.grade
        except StopIteration:
            pass


class CyanidationPlant(BaseBlendingPlant):
    """
    Based on Órdenes (2026). Models an Au-Ag cyanidation leaching plant 
    where mass is routed to Sulphide (Ore 1) or Oxide (Ore 2) stockpiles.
    """
    def __init__(self, config: CyanidationConfig, loader: BaseOreGenerator):
        super().__init__(config, loader)
        self.current_parcel_cyanide = drs.State("parcel_cyanide", 0.0)

        # In the paper, a 30% Sulphide (Ore 1) / 70% Oxide (Ore 2) blend is standard for Stage 1.
        # We initialize the stockpiles assuming this ideal 30/70 steady-state distribution.
        initial_ore2_fraction = 0.70 
        
        self.ore1_stock = drs.Level("Ore1Stock_Level", 
            initial_value=(1 - initial_ore2_fraction) * self.config.target_ore_stock_level)
        self.ore2_stock = drs.Level("Ore2Stock_Level", 
            initial_value=initial_ore2_fraction * self.config.target_ore_stock_level)

        self.total_cyanide_consumed = drs.Level("TotalCyanideConsumed_Level", initial_value=0.0)

        self._load_next_batch()

    def check_transitions(self, trigger_var: drs.Variable = None, is_upper: bool = True):
        super().check_transitions(trigger_var, is_upper)
        if trigger_var == self.ore_extraction and is_upper:
            if abs(self.ore_extraction.value - self.config.ore_to_be_extracted_during_warming_period) < 0.1:
                self.total_cyanide_consumed.value = 0.0

    @property
    def current_parcel_routing_fraction(self) -> float:
        """
        Routes mass based on Cyanide Consumption (kg/t).
        Table 2 indicates Oxides average 1.61 kg/t and Sulphides 3.22 kg/t.
        We use a midpoint threshold (~2.4 kg/t) to classify the block.
        """
        cyanide_val = self.current_parcel_cyanide.value
        oxide_sulphide_threshold = 2.41 
        
        if cyanide_val >= oxide_sulphide_threshold:
            # High-cyanide Sulphide block. Route almost 100% to Ore 1 to avoid div zero in surging.
            return 0.001 
        else:
            # Low-cyanide Oxide block. Route almost 100% to Ore 2.
            return 0.999 

    def _load_next_batch(self):
        try:
            parcel = next(self.loader)
            self.current_parcel_mass.value = parcel.mass
            # Fetch using the updated keyword, fallback to grade if needed
            self.current_parcel_cyanide.value = getattr(parcel, "cyanide_kpt", getattr(parcel, "grade", 0.0))
        except StopIteration:
            pass
