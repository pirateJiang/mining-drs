from drs.module import Module
from drs.variables import Level

class Edge:
    """A directed conduit carrying a vector of rates between two Nodes."""
    def __init__(self, name: str, source: 'Node', target: 'Node', attributes: list):
        self.name = name
        self.source = source
        self.target = target
        
        # A dictionary of continuous rates (e.g., {"mass": 0.0, "metal": 0.0})
        self.flow_rates = {attr: 0.0 for attr in attributes}
        
        # Automatically bind this edge to the nodes
        if self.source: self.source.out_edges.append(self)
        if self.target: self.target.in_edges.append(self)

    def set_rates(self, rates_dict: dict):
        """Sets the flow rates for this edge."""
        for attr, value in rates_dict.items():
            if attr in self.flow_rates:
                self.flow_rates[attr] = value

class Node(Module):
    """A generalized vertex that conserves flow and integrates accumulation."""
    def __init__(self, name: str, attributes: list, initial_values: dict = None):
        super().__init__()
        self.name = name
        self.in_edges = []
        self.out_edges = []
        initial_values = initial_values or {}
        
        # Dynamically create drs.Levels for whatever attributes the network tracks
        self.accumulations = {
            attr: Level(
                f"{name}_{attr}_Level", 
                initial_value=initial_values.get(attr, 0.0)
            ) 
            for attr in attributes
        }

    def update_internal_rates(self):
        """
        Pure mathematical conservation:
        Rate of Change (Level.rate) = Sum(Inflows) - Sum(Outflows)
        """
        # Reset rates to zero for this tick
        for level in self.accumulations.values():
            level.rate = 0.0
            
        # Add incoming rates
        for edge in self.in_edges:
            for attr, rate in edge.flow_rates.items():
                self.accumulations[attr].rate += rate
                
        # Subtract outgoing rates
        for edge in self.out_edges:
            for attr, rate in edge.flow_rates.items():
                self.accumulations[attr].rate -= rate

    def resolve_outgoing_flow(self):
        """
        To be overridden by the user. 
        This is where specific logic (like splitting flow or limiting capacity) lives.
        """
        pass

    def update_rates(self):
        """
        Nodes are orchestrated by the Network. The DRSEngine should not 
        call this directly if the node is part of a Network.
        """
        pass

class Network(Module):
    """A container that manages the execution order of a Directed Acyclic Graph."""
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.edges = []
        self._execution_order = []

    def add_node(self, node: Node):
        self.nodes.append(node)
        # Sanitize name for safe Python attribute assignment (replace spaces/hyphens with underscores)
        safe_name = node.name.replace(" ", "_").replace("-", "_")
        setattr(self, f"node_{safe_name}", node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def compile(self):
        """
        Topological Sort (Kahn's Algorithm).
        Sorts nodes so that flow calculates from source to sink.
        """
        in_degree = {node: len([e for e in node.in_edges if e.source is not None]) for node in self.nodes}
        queue = [node for node, deg in in_degree.items() if deg == 0]
        self._execution_order = []

        while queue:
            current = queue.pop(0)
            self._execution_order.append(current)
            for edge in current.out_edges:
                target = edge.target
                if target is not None:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)
                    
        if len(self._execution_order) != len(self.nodes):
            raise ValueError("Cycle detected! DRS requires a Directed Acyclic Graph.")

    def update_rates(self):
        """
        The DRSEngine calls THIS method. 
        The Network then orchestrates the Nodes in the exact sorted order.
        """
        if not self._execution_order:
            self.compile()

        # 1. Flow resolves upstream to downstream
        for node in self._execution_order:
            node.resolve_outgoing_flow()
            
        # 2. Nodes calculate their net accumulation
        for node in self.nodes:
            node.update_internal_rates()

    def check_transitions(self, trigger_var=None, is_upper: bool = True):
        """
        Delegate state transition checks to all nodes in the network.
        """
        for node in self.nodes:
            node.check_transitions(trigger_var, is_upper)
