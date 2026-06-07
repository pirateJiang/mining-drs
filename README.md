Mining-DRS: Discrete Rate Simulation Framework
Welcome to Mining-DRS! This library is a Python-based, object-oriented framework for building Discrete Rate Simulations (DRS), with a focus on mining operations and material supply chains.

If you know nothing about mining, nothing about DRS, or nothing about this system, you are in the right place. This README will guide you from ground zero to building your own complex simulations.

1. Core Concepts Explained
What is Mining (in this context)?
In this simulation framework, "mining" refers to the continuous process of extracting material from the earth and routing it through a supply chain. Specifically, we model:

Extraction: Digging up "parcels" of rock from the environment.

Physical Flow Networks: Ore moves through a Directed Acyclic Graph (DAG) of physical conduits (like conveyors or truck fleets) governed by mass conservation rules.

Stockpiles: Nodes in the network that accumulate mined ore. If a stockpile gets too full or too empty, the mine must change its operational strategy.

Milling/Processing: Sink nodes that consume ore from the stockpiles at specific rates.
The goal of a mining simulation is often to evaluate if a specific control strategy can keep the plant running smoothly without emptying critical stockpiles.

What is DRS (Discrete Rate Simulation)?
In traditional fixed-step simulations, time moves forward in small, fixed chunks (e.g., 1 hour). This can be slow and sometimes misses exact threshold crossings.

Discrete Rate Simulation (DRS) operates differently:

Variables change continuously over time at a constant rate.

Variables have thresholds (upper and lower bounds).

The simulation calculates exactly when the next variable will hit its threshold (using directional vectors).

Time "jumps" discretely to that exact moment.

At that moment, a discrete event occurs: routing splits might change, or the system might switch to a new operational mode.

2. System Architecture: The drs API
The architecture of Mining-DRS is heavily inspired by PyTorch. Everything is organized into a tree of Modules, which contain Variables and Networks.

The Main Components
drs.Network / drs.Node / drs.Edge: The physical topology of your system. Nodes accumulate or split material; Edges transfer it. The network guarantees physical flows (like mass and grade) are conserved and traced accurately.

drs.Variable / drs.Level / drs.Timer: The continuous core building blocks. These are quantities that change over time based on a rate. (Nodes automatically create Levels for their attributes).

drs.State: A discrete variable (like an Enum) that represents the current mode of operation.

drs.Module: The base class for your simulation components (e.g., a MinePlant or a MineController). Modules automatically register any variables, networks, or sub-modules assigned to them, just like nn.Module in PyTorch.

DRSEngine: The "runner." It calculates time jumps, advances time, and triggers transitions.

Telemetry: A built-in tracker that automatically records the value of all variables at every time step, exporting the history to a Pandas DataFrame for plotting.

The PyTorch → DRS Dictionary
nn.Module → drs.Module (Your physical and logical components)

nn.Sequential → drs.Network (The topological flow graph)

nn.Parameter / Tensor → drs.Variable / drs.Level (The underlying tensors holding your state)

model.forward() → model.update_rates() (Calculating the continuous dynamics based on the current state)

torch.optim.Optimizer → OperatingMode (Applying specific rules/targets to the state)

TensorBoard → Telemetry (Logging and Dashboards)

3. How the Engine Works (The Simulation Loop)
When you call engine.run(), the DRSEngine enters a continuous loop:

Check Termination: Did we hit max_time? If so, stop.

Update Rates (The Physics):

The engine calls module.update_rates().

Controllers apply their current Operating Mode, which sets policies (e.g., target milling rates, fleet routing splits).

The Network performs a topological sort, resolving all incoming and outgoing flows simultaneously across the supply chain DAG.

Calculate Time Step (dt): The engine looks at all variables, their current values, directional rates, and thresholds, determining the exact time (dt) until the closest physical constraint is hit.

Advance Time: Time jumps forward by dt. All variables update their values (value += rate * dt).

Check Transitions: The engine alerts the module of the threshold hit. The module calls check_transitions() to potentially change modes (e.g., switching to Surging Mode because a stockpile emptied).

Record Statistics: The Telemetry system takes a snapshot.

4. How to Build a Simulator (Step-by-Step)
Here is the standard workflow and best practice for creating a simulator using the graph framework.

Step 1: Define Your Physical Nodes
Subclass Node to define how physical components handle material. The network will orchestrate the execution of resolve_outgoing_flow.

Python
from drs.network import Node

class Stockpile(Node):
    def __init__(self, name):
        # Nodes automatically create Level variables for these attributes
        super().__init__(name, attributes=["mass", "grade"])
        self.target_mass_outflow = 0.0

    def set_target_outflow(self, rate: float):
        """Called by the Operating Mode to request material."""
        self.target_mass_outflow = rate

    def resolve_outgoing_flow(self):
        """Called by the Network. Pushes flow down the Edge to the Mill."""
        if not self.out_edges: return
        
        # Calculate trace concentrations safely
        safe_mass = max(1e-6, self.accumulations["mass"].value)
        grade_conc = self.accumulations["grade"].value / safe_mass
        
        # Set the physical flow rate onto the outgoing edge
        self.out_edges[0].set_rates({
            "mass": self.target_mass_outflow,
            "grade": self.target_mass_outflow * grade_conc
        })
Step 2: Define Your Operating Modes (The Logic)
Modes no longer manually calculate arithmetic. They are simply policy setters.

Python
from drs.modes import OperatingMode, RequireDecision

class NormalOperation(OperatingMode):
    @property
    def id(self) -> int: return 0
    @property
    def name(self) -> str: return "NORMAL"
    
    def apply_dynamics(self, model):
        # Set the top-level policy. The Network graph handles the physical routing.
        model.plant.ore_stock.set_target_outflow(100.0)

    def check_end_conditions(self, model):
        # If the stockpile hits its physical lower threshold, require a decision
        if model.plant.ore_stock.accumulations["mass"].value <= 0:
            return RequireDecision()
        return None
Step 3: Wire the Graph with the Fluent API (>>)
Create a drs.Module to hold your plant. Add your nodes to a Network, and wire them together using the bitwise right-shift operator (>>).

Python
from drs import drs
from drs.network import Network

class MinePlant(drs.Module):
    def __init__(self):
        super().__init__()
        # 1. Instantiate Nodes
        self.fleet = Node("Fleet", attributes=["mass", "grade"])
        self.ore_stock = Stockpile("Ore_Stock")
        self.mill = Node("Mill", attributes=["mass", "grade"])
        
        # 2. Build & Wire the Network Graph
        self.supply_network = Network()
        self.supply_network.add_node(self.fleet)
        self.supply_network.add_node(self.ore_stock)
        self.supply_network.add_node(self.mill)
        
        # FLUENT API: Wires the Fleet to the Stockpile, and the Stockpile to the Mill!
        self.fleet >> self.ore_stock >> self.mill
        
        self.supply_network.compile()

    def update_rates(self):
        # The network resolves all rates topologically
        self.supply_network.update_rates()
Step 4: Run, Visualize, and Plot
You can instantly visualize the topology of your supply chain before running the simulation to ensure your edges are wired correctly.

Python
from drs import DRSEngine
from drs.plot import build_dashboard, plot_time_series

class ExampleMineModel(drs.Module):
    # ... sets up plant, controller, and telemetry ...

sim = ExampleMineModel()

# 1. Visually verify your flow network! (Requires networkx & matplotlib)
sim.plant.supply_network.draw(title="Mine Supply Topology")

# 2. Run the Engine
engine = DRSEngine(sim)
engine.run(max_time=365.0)

# 3. Plot the telemetry
df = sim.telemetry.to_dataframe()
dashboard = build_dashboard(df, configs=[
    {"func": plot_time_series, "kwargs": {"y_columns": ["Ore_Stock_mass"]}}
])
dashboard.savefig("results.png")
5. Conventions & Best Practices
Separation of Concerns: Let the Network Graph handle physical limits, mass balance, and arithmetic. Let the Modes handle strategy and desired targets.

Directional Thresholds: Ensure you check the rate when querying thresholds in modes (e.g., if var.rate < 0 and var.value <= target_floor) to avoid zero-tick ping-pong deadlocks when surging.

Visual Debugging: Always call supply_network.draw() when adding a new physical component to guarantee your Splitters and Sinks are routed correctly.

Zeroing Rates: You don't need to manually reset network flow rates to zero every cycle. The DRSEngine zeroes them automatically before the topological sort.

6. API Reference: Core Classes
Network Topology (drs.network)
Network: The directed acyclic graph orchestrator.

add_node(node) / add_edge(edge): Registers components.

compile(): Validates the DAG and pre-computes the topological sort order.

update_rates(): Steps through the sorted nodes, calling resolve_outgoing_flow.

draw(): Renders an interactive or static diagram of the physical layout using networkx.

Node: Represents physical stations (Stockpiles, Fleets, Mills).

__rshift__(other): The >> operator. Syntax sugar to create an Edge pointing to another node.

resolve_outgoing_flow(): Override. Define how accumulated flow is routed into self.out_edges.

Edge: The physical conduit. Holds a flow_rates dictionary connecting a source to a target.

Variables (drs.variables)
drs.Variable(name, initial_value, rate): The continuous base class. Includes directional threshold triggers.

drs.Level: Accumulates or depletes (automatically managed inside Nodes).

drs.State: Represents discrete categories (like Modes). Time-stepping ignores its rates, but Telemetry tracks its changes.

Simulation Loop (drs.engine & drs.module)
drs.Module: The base class for logic components (Controllers, overall Models).

DRSEngine(model): The runner class. Handles calculating dt and advancing time safely without breaching boundaries.
