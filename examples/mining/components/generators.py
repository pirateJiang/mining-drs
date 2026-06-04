import random
import numpy as np
import gstools as gs
from drs.data import BaseOreGenerator, OreParcel
from .config import ConcentratorConfig, CyanidationConfig


class StochasticFaciesGradeGenerator(BaseOreGenerator):
    """The random math version, matching your current logic."""

    def __init__(self, config: ConcentratorConfig):
        self.config = config
        self.next_is_new_facies = True
        self.current_grade = config.mean_grade
        self.first_call = True

    def __iter__(self):
        return self

    def __next__(self) -> OreParcel:
        c = self.config

        if self.first_call:
            self.first_call = False
            return OreParcel(mass=40000.0, grade=c.mean_grade)

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

        return OreParcel(mass=mass, grade=self.current_grade)


class CyanideGeostatisticalBlockGenerator(BaseOreGenerator):
    """Generates equiprobable 2D spatial block models using Sequential Gaussian Simulation."""

    def __init__(self, config: CyanidationConfig):
        self.config = config

        # 1. Define the variogram model (matching Table 3 in the paper)
        # The paper uses a nugget + two spherical models with anisotropy
        angles = np.deg2rad(35)  # Dip of 35 degrees
        self.model = gs.Spherical(
            dim=2, var=0.31, len_scale=25, nugget=0.15
        ) + gs.Spherical(dim=2, var=0.54, len_scale=150)

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
            # Fallback to linear if standard deviation is 0 or mean is 0
            cyanide = (
                field * self.config.std_dev_cyanide_consumption
                + self.config.mean_cyanide_consumption
            )

        self.cyanide_field = np.maximum(cyanide, 0.0)

    def create_bench_and_fill_sequence(self):
        # TODO: A simple raster scan is an acceptable approximation here, but for strict
        # fidelity to the paper, the coordinates should be indexed according to the exact
        # staggered stoping sequence depicted in Figure 14 (dictated by horizontal/long-hole drilling).

        # Yield cyanide consumption traversing the block model (bench by bench, top-down)
        # Assuming y is elevation, mine from highest y to lowest y
        for y_idx in reversed(range(self.cyanide_field.shape[1])):
            for x_idx in range(self.cyanide_field.shape[0]):
                au_eq = self.au_eq_field[x_idx, y_idx]
                cyanide_consumption = self.cyanide_field[x_idx, y_idx]

                # Discard blocks (Waste 'W') where the deterministic Au_eq grade is below the 2.8 g/t cut-off
                if au_eq >= 2.8:
                    yield cyanide_consumption

    def __iter__(self):
        return self

    def __next__(self) -> OreParcel:
        while True:
            try:
                cyanide_val = next(self.mining_sequence)
                break
            except StopIteration:
                # If we exhaust the block model, generate a new cyanide realization (equiprobable model)
                self.generate_new_cyanide_realization()
                self.mining_sequence = self.create_bench_and_fill_sequence()

        # The paper blocks are 4m x 4m, we'll randomize mass within the configured bounds
        # or we could use a fixed mass for a 4x4xH block, but we stick to config bounds
        mass = random.uniform(self.config.min_ore_mass, self.config.max_ore_mass)

        # We pass cyanide consumption under the cyanide_kpt kwarg
        return OreParcel(mass=mass, cyanide_kpt=cyanide_val)
