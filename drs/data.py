from dataclasses import dataclass
from abc import ABC, abstractmethod


class MaterialFlow:
    """A dynamic bundle of continuous DRS rates."""

    def __init__(self, mass_rate: float, attributes: dict = None):
        self.mass_rate = mass_rate
        # Dictionary storing rates of attributes (e.g., {"metal": 2500.0, "cyanide": 3200.0})
        self.attributes = attributes if attributes else {}

    def __mul__(self, fraction: float):
        return MaterialFlow(
            mass_rate=self.mass_rate * fraction,
            attributes={k: v * fraction for k, v in self.attributes.items()}
        )

    def __rmul__(self, fraction: float):
        return self.__mul__(fraction)


# TODO: these are specific to mining and possibly should be moved.


# TODO: Ore parcel is mining specific, but maybe this represents something in the DRS or graph thing that can be abstracetd and kept here.
class OreParcel:
    """The standard unit of data passed from geology to the plant."""

    def __init__(self, mass: float, grade: float = 0.0, **kwargs):
        self.mass = mass
        self.grade = grade

        # Dynamically assign any other passed attributes (like cyanide_kpt, hardness, etc.)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        attrs = ", ".join(f"{k}={v}" for k, v in self.__dict__.items())
        return f"OreParcel({attrs})"


# Ore Loaders or Ore Generators?
class BaseOreGenerator(ABC):
    """The abstract base class for all geology data sources."""

    def __iter__(self):
        return self

    @abstractmethod
    def __next__(self) -> OreParcel:
        """Must yield the next parcel of ore, or raise StopIteration."""
        pass
