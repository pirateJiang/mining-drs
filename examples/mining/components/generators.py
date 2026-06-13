import random
import numpy as np

from drs.module import drs
from drs.flow import Flow
from .config import ConcentratorConfig


class StochasticFaciesGradeGenerator(drs.DataSource):
    """Random facies-based grade generation for the Concentrator model."""

    def __init__(self, config: ConcentratorConfig):
        super().__init__()
        self.config = config
        self.next_is_new_facies = True
        self.current_grade = config.mean_grade
        self.first_call = True

    def forward(self):
        return Flow(value=next(self))

    def __next__(self) -> drs.DataPoint:
        c = self.config

        if self.first_call:
            self.first_call = False
            return drs.DataPoint(mass=40000.0, grade=c.mean_grade)

        mass = random.uniform(c.min_ore_mass, c.max_ore_mass)

        if self.next_is_new_facies:
            if c.std_dev_grade != 0:
                grade = random.gauss(c.mean_grade, c.std_dev_grade)
            else:
                grade = c.mean_grade
        else:
            grade = self.current_grade + c.variation_same_facies * random.uniform(-1, 1)

        self.current_grade = max(grade, 0.0)
        self.next_is_new_facies = random.random() <= c.prob_new_facies

        return drs.DataPoint(mass=mass, grade=self.current_grade)



