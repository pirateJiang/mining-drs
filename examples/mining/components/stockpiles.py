from typing import List, Dict, Optional
from drs.network import Node

class Stockpile(Node):
    def __init__(
        self,
        name: str,
        expected_attributes: List[str],
        initial_mass: float = 0.0,
        initial_attributes: Optional[Dict[str, float]] = None,
    ):
        # Initialize Node with mass and trace attributes
        super().__init__(name, attributes=["mass"] + expected_attributes)
        self.expected_attributes = expected_attributes
        self.target_mass_outflow = 0.0
        
        # Backwards Compatibility: Force Level names to match legacy telemetry perfectly
        self.accumulations["mass"].name = f"{name}_mass"
        self.accumulations["mass"].value = initial_mass
        
        initial_attributes = initial_attributes or {}
        for attr in expected_attributes:
            self.accumulations[attr].name = f"{name}_{attr}"
            self.accumulations[attr].value = initial_attributes.get(attr, 0.0)

        # Backwards Compatibility: Provide original variable aliases used by the Engine/Plots
        self.mass = self.accumulations["mass"]
        self.attributes = {attr: self.accumulations[attr] for attr in expected_attributes}

    def current_concentration(self, attr: str) -> float:
        if attr not in self.attributes:
            return 0.0
        safe_mass = max(1e-6, self.mass.value)
        return self.attributes[attr].value / safe_mass

    def set_target_outflow(self, mass_rate: float):
        """Replaces take_outflow(). Defines the mass requested by the mill for this tick."""
        self.target_mass_outflow = mass_rate

    def resolve_outgoing_flow(self):
        """The Network orchestrates this. Automatically applies trace concentrations to outflows."""
        if not self.out_edges:
            return
        
        # Push proportional trace elements down the outgoing edge to the mill
        out_edge = self.out_edges[0]
        
        # Prevent deadlock: clamp outflow if stockpile is empty
        actual_outflow = self.target_mass_outflow
        if self.mass.value <= 1e-6:
            inflow = sum(edge.flow_rates.get("mass", 0.0) for edge in self.in_edges)
            actual_outflow = min(actual_outflow, inflow)
            
        rates = {"mass": actual_outflow}
        for attr in self.expected_attributes:
            rates[attr] = actual_outflow * self.current_concentration(attr)
            
        out_edge.set_rates(rates)
