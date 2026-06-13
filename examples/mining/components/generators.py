import random
import numpy as np

from drs.module import drs
from drs.flow import Flow
from .config import ConcentratorConfig


class StochasticFaciesGradeGenerator(drs.DataSource):
    """Random facies-based ore_fraction generation for the Concentrator model."""

    def __init__(self, config: ConcentratorConfig):
        super().__init__()
        self.config = config
        self.next_is_new_facies = True
        self.current_ore_fraction = config.mean_ore_fraction
        self.first_call = True

    def forward(self):
        return Flow(value=next(self))

    def __next__(self) -> drs.DataPoint:
        c = self.config

        if self.first_call:
            self.first_call = False
            return drs.DataPoint(mass=40000.0, ore_fraction=c.mean_ore_fraction)

        mass = random.uniform(c.min_ore_mass, c.max_ore_mass)

        if self.next_is_new_facies:
            if c.std_dev_ore_fraction != 0:
                ore_fraction = random.gauss(c.mean_ore_fraction, c.std_dev_ore_fraction)
            else:
                ore_fraction = c.mean_ore_fraction
        else:
            ore_fraction = self.current_ore_fraction + c.variation_same_facies * random.uniform(-1, 1)

        self.current_ore_fraction = max(ore_fraction, 0.0)
        self.next_is_new_facies = random.random() <= c.prob_new_facies

        return drs.DataPoint(mass=mass, ore_fraction=self.current_ore_fraction)



