from drs.module import drs
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

    def forward(self, mode: OperatingMode):
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

        targets = mode.get_target_rates(self.parent)
        self.true_ore_extraction.rate = targets.extraction_rate
        self.true_ore_extracted_from_current_parcel.rate = targets.extraction_rate


class ConcentratorMineFace(BaseMineFace):
    def __init__(self, config: ConcentratorConfig, loader: drs.DataSource):
        super().__init__(config, loader)
        self.true_current_parcel_grade = drs.Variable("true_parcel_grade", 0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel = self.loader.next()
            self.true_current_parcel_mass.value = parcel.mass
            self.true_current_parcel_grade.value = parcel.grade
        except StopIteration:
            pass

    def forward(self, mode: OperatingMode):
        super().forward(mode)


class CyanidationMineFace(BaseMineFace):
    def __init__(self, config: CyanidationConfig, loader: drs.DataSource):
        super().__init__(config, loader)
        self.true_current_parcel_cyanide = drs.Variable("true_parcel_cyanide", 0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel = self.loader.next()
            self.true_current_parcel_mass.value = parcel.mass
            self.true_current_parcel_cyanide.value = getattr(
                parcel, "cyanide_kpt", getattr(parcel, "grade", 0.0)
            )
        except StopIteration:
            pass

    def forward(self, mode: OperatingMode):
        super().forward(mode)


# ---------------------------------------------------------
# FLEET LOGISTICS
# ---------------------------------------------------------


class BaseFleetLogistics(drs.Module):
    def __init__(self, config, mine, expected_attributes: list):
        super().__init__()
        self.name = "Fleet"
        self.config = config
        self.mine = mine
        self.expected_attributes = expected_attributes
        self.fraction_to_ore2 = drs.Variable("fraction_to_ore2", 0.0)

    def calculate_routing_fraction(self) -> float:
        raise NotImplementedError(
            "Subclasses must define how routing fraction is calculated."
        )

    def forward(self):
        self.fraction_to_ore2.value = self.calculate_routing_fraction()


class ConcentratorFleet(BaseFleetLogistics):
    def __init__(self, config, mine):
        super().__init__(config, mine, expected_attributes=["grade"])

    def calculate_routing_fraction(self) -> float:
        grade = self.mine.true_current_parcel_grade.value
        return grade / self.config.grade_percentage_scale


class CyanidationFleet(BaseFleetLogistics):
    def __init__(self, config, mine):
        super().__init__(config, mine, expected_attributes=["cyanide"])

    def calculate_routing_fraction(self) -> float:
        cyanide = self.mine.true_current_parcel_cyanide.value
        oxide_sulphide_threshold = 2.41
        if cyanide >= oxide_sulphide_threshold:
            return 0.001
        else:
            return 0.999


# ---------------------------------------------------------
# METALLURGICAL PLANT
# ---------------------------------------------------------


class BaseMetallurgicalPlant(drs.Module):
    def __init__(self, config, fleet: BaseFleetLogistics):
        super().__init__()
        self.config = config
        self.fleet = fleet

        self.true_ore_stock = drs.Level(
            "TrueOreStock_Level", initial_value=self.config.target_ore_stock_level
        )

        self.true_total_ore_milled = drs.Level(
            "TrueTotalOreMilled_Level", initial_value=0.0
        )

        # To be initialized by subclass based on fractions
        self.true_ore1_stock = None
        self.true_ore2_stock = None

    def forward(self):
        ore1_rate = self.true_ore1_stock.actual_outflow.value
        ore2_rate = self.true_ore2_stock.actual_outflow.value
        self.true_total_ore_milled.rate = ore1_rate + ore2_rate
        self.true_ore_stock.rate = (
            self.true_ore1_stock.mass.rate + self.true_ore2_stock.mass.rate
        )

        if self.true_ore_stock.rate < 0:
            self.true_ore_stock.lower_threshold = 0.0


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
            initial_attributes={"grade": initial_mass1 * self.config.mean_grade},
        )

        initial_mass2 = initial_fraction * self.config.target_ore_stock_level
        self.true_ore2_stock = Stockpile(
            name="TrueOre2Stock",
            expected_attributes=["grade"],
            initial_mass=initial_mass2,
            initial_attributes={"grade": initial_mass2 * self.config.mean_grade},
        )

    def forward(self):
        super().forward()


class CyanidationPlant(BaseMetallurgicalPlant):
    def __init__(self, config: CyanidationConfig, fleet: BaseFleetLogistics):
        super().__init__(config, fleet)

        initial_ore2_fraction = 0.70

        initial_mass1 = (1 - initial_ore2_fraction) * self.config.target_ore_stock_level
        self.true_ore1_stock = Stockpile(
            name="TrueOre1Stock",
            expected_attributes=["cyanide"],
            initial_mass=initial_mass1,
            initial_attributes={
                "cyanide": initial_mass1 * self.config.mean_cyanide_consumption
            },
        )

        initial_mass2 = initial_ore2_fraction * self.config.target_ore_stock_level
        self.true_ore2_stock = Stockpile(
            name="TrueOre2Stock",
            expected_attributes=["cyanide"],
            initial_mass=initial_mass2,
            initial_attributes={
                "cyanide": initial_mass2 * self.config.mean_cyanide_consumption
            },
        )

        self.true_total_cyanide_consumed = drs.Level(
            "TrueTotalCyanideConsumed_Level", initial_value=0.0
        )
        self.true_current_mill_kpt = drs.Variable("true_current_mill_kpt", 0.0)

    def forward(self):
        if (
            abs(
                self.fleet.mine.true_ore_extraction.value
                - self.config.ore_to_be_extracted_during_warming_period
            )
            < 1e-6
        ):
            self.true_total_cyanide_consumed.value = 0.0
            self.true_total_ore_milled.value = 0.0

        super().forward()

        s1, s2 = self.true_ore1_stock, self.true_ore2_stock
        ore1_cyanide = s1.actual_outflow.value * s1.current_concentration("cyanide")
        ore2_cyanide = s2.actual_outflow.value * s2.current_concentration("cyanide")
        cyanide_consumed = ore1_cyanide + ore2_cyanide
        self.true_total_cyanide_consumed.rate = cyanide_consumed

        if self.true_total_ore_milled.rate > 0:
            self.true_current_mill_kpt.value = (
                self.true_total_cyanide_consumed.rate / self.true_total_ore_milled.rate
            )
        else:
            self.true_current_mill_kpt.value = 0.0
