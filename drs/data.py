from dataclasses import dataclass
from abc import ABC, abstractmethod

# TODO: these are specific to mining and possibly should be moved.


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
