import random
import numpy as np
import gstools as gs
from drs.module import drs
from .config import ConcentratorConfig, CyanidationConfig


class StochasticFaciesGradeGenerator(drs.DataSource):
    """Random facies-based grade generation for the Concentrator model."""

    def __init__(self, config: ConcentratorConfig):
        super().__init__()
        self.config = config
        self.next_is_new_facies = True
        self.current_grade = config.mean_grade
        self.first_call = True

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


class CyanideGeostatisticalBlockGenerator(drs.DataSource):
    """Generates equiprobable 2D spatial block models using Sequential Gaussian Simulation."""

    def __init__(self, config: CyanidationConfig):
        super().__init__()
        self.config = config

        # 1. Define the variogram model (matching Table 3 in the paper)
        # The paper uses a nugget + two spherical models with anisotropy
        angles = np.deg2rad(35)  # Dip of 35 degrees
        self.model = gs.Spherical(
            dim=2, var=0.31, len_scale=[25, 15], nugget=0.15, angles=angles
        ) + gs.Spherical(dim=2, var=0.54, len_scale=[150, 90], angles=angles)

        # 2. Setup the spatial grid (e.g., the 2D bench-and-fill area)
        self.x = np.arange(0, 1200, 4)  # 4m x 4m blocks
        self.y = np.arange(100, 600, 4)

        # 3. Generate the static, deterministic Au_eq grade mask (identical across all replicas)
        # We use a fixed seed to ensure the waste/ore boundaries never change
        au_model = gs.Spherical(dim=2, var=1.0, len_scale=50)
        srf_au = gs.SRF(au_model, seed=101010)
        au_raw = srf_au.structured([self.x, self.y])
        # Transform to a distribution where ~50% might be above 2.8 (e.g., mean 3.0, std 1.0)
        self.au_eq_field = au_raw * 1.0 + 3.0

        # 4. Generate the stochastic cyanide consumption field
        self.srf_cyanide = gs.SRF(self.model)
        self.generate_new_cyanide_realization()

        # Setup an iterator to "mine" through this grid
        self.mining_sequence = self.create_bench_and_fill_sequence()

    def generate_new_cyanide_realization(self):
        field = self.srf_cyanide.structured([self.x, self.y])

        # TODO: In a fully faithful implementation, use an empirical CDF or an anamorphosis
        # mapping for the normal score back-transformation to the raw cyanide consumption distribution.
        # For simplicity, we approximate this back-transformation using a log-normal distribution.
        m = self.config.mean_cyanide_consumption
        v = self.config.std_dev_cyanide_consumption**2

        if m > 0 and v > 0:
            sigma_sq = np.log(1 + v / (m**2))
            mu = np.log(m) - sigma_sq / 2.0
            cyanide = np.exp(mu + np.sqrt(sigma_sq) * field)
        else:
            cyanide = (
                field * self.config.std_dev_cyanide_consumption
                + self.config.mean_cyanide_consumption
            )

        self.cyanide_field = np.maximum(cyanide, 0.0)

    def create_bench_and_fill_sequence(self):
        # Yield cyanide consumption traversing the block model (bench by bench, top-down)
        for y_idx in reversed(range(self.cyanide_field.shape[1])):
            for x_idx in range(self.cyanide_field.shape[0]):
                au_eq = self.au_eq_field[x_idx, y_idx]
                cyanide_consumption = self.cyanide_field[x_idx, y_idx]

                if au_eq >= 2.8:
                    yield cyanide_consumption

    def __next__(self) -> drs.DataPoint:
        while True:
            try:
                cyanide_val = next(self.mining_sequence)
                break
            except StopIteration:
                self.generate_new_cyanide_realization()
                self.mining_sequence = self.create_bench_and_fill_sequence()

        mass = random.uniform(self.config.min_ore_mass, self.config.max_ore_mass)
        return drs.DataPoint(mass=mass, cyanide_kpt=cyanide_val)
