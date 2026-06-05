from drs.module import drs
from .config import ConcentratorConfig, CyanidationConfig
from .supply_chain import BaseMineFace, BaseFleetLogistics, BaseMetallurgicalPlant

class BaseSensorNetwork(drs.Module):
    """
    Virtual Instrument layer that mediates data between the physical supply chain and the controller.
    Allows for simulating assay delays, instrument noise, and data masking.
    """
    def __init__(self, config, mine: BaseMineFace, fleet: BaseFleetLogistics, plant: BaseMetallurgicalPlant):
        super().__init__()
        self.config = config
        self.mine = mine
        self.fleet = fleet
        self.plant = plant

        # Mirrored states
        self.belief_current_parcel_mass = drs.State("belief_parcel_mass", 0.0)
        self.belief_ore_stock = drs.Level("BeliefOreStock_Level", initial_value=self.config.target_ore_stock_level)

        # To be initialized by subclass
        self.belief_ore1_stock = None
        self.belief_ore2_stock = None

    @property
    def belief_routing_fraction(self) -> float:
        raise NotImplementedError("Subclasses must define how to calculate the routing fraction.")

    def update_rates(self):
        # Perfect pass-through
        self.belief_current_parcel_mass.value = self.mine.true_current_parcel_mass.value
        self.belief_ore_stock.rate = self.plant.true_ore_stock.rate
        
        if self.belief_ore1_stock is not None:
            self.belief_ore1_stock.rate = self.plant.true_ore1_stock.mass.rate
            self.belief_ore1_stock.lower_threshold = self.plant.true_ore1_stock.mass.lower_threshold
        if self.belief_ore2_stock is not None:
            self.belief_ore2_stock.rate = self.plant.true_ore2_stock.mass.rate
            self.belief_ore2_stock.lower_threshold = self.plant.true_ore2_stock.mass.lower_threshold
            
        self.belief_ore_stock.lower_threshold = self.plant.true_ore_stock.lower_threshold


import random
import numpy as np

class ConcentratorSensorNetwork(BaseSensorNetwork):
    def __init__(self, config: ConcentratorConfig, mine, fleet, plant):
        super().__init__(config, mine, fleet, plant)
        
        initial_fraction = self.config.mean_grade / self.config.grade_percentage_scale

        self.belief_ore1_stock = drs.Level("BeliefOre1Stock_Level", initial_value=(1 - initial_fraction) * self.config.target_ore_stock_level)
        self.belief_ore2_stock = drs.Level("BeliefOre2Stock_Level", initial_value=initial_fraction * self.config.target_ore_stock_level)

        self.belief_current_parcel_grade = drs.State("belief_parcel_grade", 0.0)
        self.belief_ore1_grade = drs.State("belief_ore1_grade", 0.0)
        self.belief_ore2_grade = drs.State("belief_ore2_grade", 0.0)

    @property
    def belief_routing_fraction(self) -> float:
        return self.belief_current_parcel_grade.value / self.config.grade_percentage_scale

    def update_rates(self):
        super().update_rates()
        self.belief_current_parcel_grade.value = self.mine.true_current_parcel_grade.value

        true_ore1_grade = self.plant.true_ore1_stock.current_concentration("grade")
        self.belief_ore1_grade.value = max(0.0, true_ore1_grade + float(np.random.normal(0, 0.1)))

        true_ore2_grade = self.plant.true_ore2_stock.current_concentration("grade")
        self.belief_ore2_grade.value = max(0.0, true_ore2_grade + float(np.random.normal(0, 0.1)))


class CyanidationSensorNetwork(BaseSensorNetwork):
    def __init__(self, config: CyanidationConfig, mine, fleet, plant):
        super().__init__(config, mine, fleet, plant)
        
        initial_ore2_fraction = 0.70

        self.belief_ore1_stock = drs.Level("BeliefOre1Stock_Level", initial_value=(1 - initial_ore2_fraction) * self.config.target_ore_stock_level)
        self.belief_ore2_stock = drs.Level("BeliefOre2Stock_Level", initial_value=initial_ore2_fraction * self.config.target_ore_stock_level)

        self.belief_current_parcel_cyanide = drs.State("belief_parcel_cyanide", 0.0)
        self.belief_ore1_cyanide = drs.State("belief_ore1_cyanide", 0.0)
        self.belief_ore2_cyanide = drs.State("belief_ore2_cyanide", 0.0)

    @property
    def belief_routing_fraction(self) -> float:
        cyanide_val = self.belief_current_parcel_cyanide.value
        oxide_sulphide_threshold = 2.41
        if cyanide_val >= oxide_sulphide_threshold:
            return 0.001
        else:
            return 0.999

    def update_rates(self):
        super().update_rates()
        self.belief_current_parcel_cyanide.value = self.mine.true_current_parcel_cyanide.value

        true_ore1_cyanide = self.plant.true_ore1_stock.current_concentration("cyanide")
        self.belief_ore1_cyanide.value = max(0.0, true_ore1_cyanide + random.gauss(0, 0.1))

        true_ore2_cyanide = self.plant.true_ore2_stock.current_concentration("cyanide")
        self.belief_ore2_cyanide.value = max(0.0, true_ore2_cyanide + random.gauss(0, 0.1))
