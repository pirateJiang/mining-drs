from .module import drs
from .engine import DRSEngine
from .data import OreParcel, BaseOreGenerator, MaterialFlow
from .network import Edge, Node, Network

# Attach network objects to the drs namespace class
drs.Edge = Edge
drs.Node = Node
drs.Network = Network

__all__ = ["drs", "DRSEngine", "OreParcel", "BaseOreGenerator", "MaterialFlow"]
