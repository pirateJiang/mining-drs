from typing import List, Dict, Optional
from drs.module import Module
from drs.variables import Level
from drs.data import MaterialFlow


# TODO: should this be in nodes.py does that make sense? also this is mining specific. i dont want mining specific stuff in my DRS. Maybe it would be interesting though to try and make this DRS both a DRS and a sort of acyclical graph type thing. So have a concept of a Node Module and a Edge Module or something.
class Stockpile(Module):
    """
    A physical stockpile node that integrates mass and trace attributes dynamically.
    Instead of tracking only mass, it integrates every expected attribute of a MaterialFlow.
    """

    def __init__(
        self,
        name: str,
        expected_attributes: List[str],
        initial_mass: float = 0.0,
        initial_attributes: Optional[Dict[str, float]] = None,
    ):
        super().__init__()
        self.name = name
        self.expected_attributes = expected_attributes

        # Mass level (the Carrier Fluid)
        self.mass = Level(f"{name}_mass", initial_value=initial_mass)

        # Dictionary storing Level variables for each trace element/attribute
        self.attributes: Dict[str, Level] = {}

        initial_attributes = initial_attributes or {}

        for attr in expected_attributes:
            init_val = initial_attributes.get(attr, 0.0)
            # Create a Level for this attribute
            level = Level(f"{name}_{attr}", initial_value=init_val)
            self.attributes[attr] = level
            # We must register the Variable to the Module so the engine finds it
            setattr(self, f"_attr_level_{attr}", level)

    def apply_inflow(self, flow: MaterialFlow):
        """Applies an incoming MaterialFlow to the rates of the stockpile."""
        self.mass.rate += flow.mass_rate
        for attr, attr_rate in flow.attributes.items():
            if attr in self.attributes:
                self.attributes[attr].rate += attr_rate

    def apply_outflow(self, flow: MaterialFlow):
        """Applies an outgoing MaterialFlow to the rates of the stockpile."""
        self.mass.rate -= flow.mass_rate
        for attr, attr_rate in flow.attributes.items():
            if attr in self.attributes:
                self.attributes[attr].rate -= attr_rate

    def current_concentration(self, attr: str) -> float:
        """Calculates the current concentration of a trace attribute."""
        if attr not in self.attributes:
            return 0.0
        safe_mass = max(1e-6, self.mass.value)
        return self.attributes[attr].value / safe_mass

    def take_outflow(self, mass_rate: float) -> MaterialFlow:
        """Constructs an outgoing MaterialFlow based on current concentration and applies it to rates."""
        attrs = {}
        for attr in self.attributes.keys():
            attrs[attr] = mass_rate * self.current_concentration(attr)
            
        flow = MaterialFlow(mass_rate, attributes=attrs)
        self.apply_outflow(flow)
        return flow
