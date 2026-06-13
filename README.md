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
The architecture of Mining-DRS is heavily inspired by PyTorch. Everything is organized into a tree of semantic Modules, which own Variables and can nest other Modules.

The Main Components
drs.Variable / drs.Level / drs.Timer: The continuous core building blocks. These are quantities that change over time based on a rate. (Nodes automatically create Levels for their attributes).

drs.State: A discrete variable (like an Enum) that represents the current mode of operation.

drs.Module: The base class for your simulation components (e.g., a Plant, Fleet, Truck, Mine, or Controller). Modules automatically register any variables or sub-modules assigned to them, just like nn.Module in PyTorch.

Compatibility API: drs.Network / drs.Node / drs.Edge are deprecated. Existing graph-based models still run, but new models should represent physical components as Modules that own their Level state directly.

DRSEngine: The "runner." It calculates time jumps, advances time, and triggers transitions.

Telemetry: A built-in tracker that automatically records the value of all variables at every time step, exporting the history to a Pandas DataFrame for plotting.

The PyTorch → DRS Dictionary
nn.Module → drs.Module (Your physical and logical components)

nn.Sequential → Nested drs.Module objects (The semantic model tree)

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

Your semantic Modules update their owned Level rates and explicitly delegate to nested Modules where needed.

Calculate Time Step (dt): The engine looks at all variables, their current values, directional rates, and thresholds, determining the exact time (dt) until the closest physical constraint is hit.

Advance Time: Time jumps forward by dt. All variables update their values (value += rate * dt).

Check Transitions: The engine alerts the module of the threshold hit. The module calls check_transitions() to potentially change modes (e.g., switching to Surging Mode because a stockpile emptied).

Record Statistics: The Telemetry system takes a snapshot.

4. How to Build a Simulator (Step-by-Step)
Here is the standard workflow and best practice for creating a simulator using semantic Modules.

Step 1: Define Your Physical Modules
Subclass drs.Module to define how physical components own and update material state.

Python
from drs import drs

class Truck(drs.Module):
    def __init__(self, capacity):
        super().__init__()
        self.payload = drs.Level("Payload")
        self.capacity = capacity

    def update_rates(self):
        # Truck-specific continuous dynamics live here.
        pass

class Fleet(drs.Module):
    def __init__(self, num_trucks):
        super().__init__()
        for i in range(num_trucks):
            setattr(self, f"truck_{i}", Truck(capacity=50))
        self.total_delivered = drs.Level("Total_Delivered")

    def update_rates(self):
        for truck in self._modules.values():
            truck.update_rates()
            if truck.payload.value == truck.capacity:
                self.total_delivered.rate += truck.payload.value
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
        # Set policies directly on semantic modules.
        model.plant.fleet.target_delivery_rate = 100.0

    def check_end_conditions(self, model):
        # If a physical Level hits a bound, require a decision.
        if model.plant.fleet.total_delivered.value <= 0:
            return RequireDecision()
        return None
Step 3: Compose Modules Hierarchically
Create a top-level drs.Module that owns your plant, mine, fleet, controller, and any nested components.

Python
from drs import drs

class MinePlant(drs.Module):
    def __init__(self):
        super().__init__()
        self.fleet = Fleet(num_trucks=3)
        self.ore_stock = drs.Level("Ore_Stock")
        self.mill_feed = drs.Level("Mill_Feed")

    def update_rates(self):
        self.fleet.update_rates()
        self.mill_feed.rate = min(100.0, self.ore_stock.value)
Step 4: Run and Plot

Python
from drs import DRSEngine
from drs.plot import build_dashboard, plot_time_series

class ExampleMineModel(drs.Module):
    # ... sets up plant, controller, and telemetry ...

sim = ExampleMineModel()

# 1. Run the Engine
engine = DRSEngine(sim)
engine.run(max_time=365.0)

# 2. Plot the telemetry
df = sim.telemetry.to_dataframe()
dashboard = build_dashboard(df, configs=[
    {"func": plot_time_series, "kwargs": {"y_columns": ["Ore_Stock_mass"]}}
])
dashboard.savefig("results.png")

### Step 5: Data Sources (Streaming Data with DataSource / DataPoint)

In real mining operations, ore doesn't appear magically — it arrives as a stream of heterogeneous parcels, each with its own mass, grade, and geochemistry. The `drs.DataSource` / `drs.DataPoint` pair gives you a standard way to model this:

- **`drs.DataSource`** is an iterator (like PyTorch's `DataLoader`). Subclass it and implement `__next__` to yield batches of data.
- **`drs.DataPoint`** is a lightweight container. Fields are accessed as attributes — pass any keyword args to `__init__`.

Python
from drs import drs
import random

class TruckDataSource(drs.DataSource):
    def __init__(self, avg_mass=50.0):
        super().__init__()
        self.avg_mass = avg_mass
        self.count = 0
        self.max_loads = 10

    def __next__(self) -> drs.DataPoint:
        if self.count >= self.max_loads:
            raise StopIteration
        self.count += 1
        mass = random.uniform(0.8, 1.2) * self.avg_mass
        grade = random.uniform(0.5, 1.5)
        return drs.DataPoint(mass=mass, grade=grade)

# Usage in a Module:
class TruckUnloader(drs.Module):
    def __init__(self, source: drs.DataSource):
        super().__init__()
        self.source = source
        self.parcel_mass = drs.Variable("parcel_mass", 0.0)
        self.parcel_grade = drs.Variable("parcel_grade", 0.0)

    def load_next(self):
        try:
            parcel = self.source.next()  # or: next(self.source)
            self.parcel_mass.value = parcel.mass
            self.parcel_grade.value = parcel.grade
        except StopIteration:
            pass

You can also iterate directly:

Python
for parcel in source:
    print(parcel.mass, parcel.grade)

DataSources compose naturally with the engine — they are `drs.Module` subclasses, so they appear in `named_modules()`, `variables()`, and the visualization system. The mining example ships with two built-in sources:

- `StochasticFaciesGenerator` — random facies-based grade generation
- `CyanideGeostatisticalBlockGenerator` — conditional simulation block models with Gaussian Sequential Simulation

5. Conventions & Best Practices
Separation of Concerns: Let physical Modules own state and dynamics. Let Modes handle strategy and desired targets.

Directional Thresholds: Ensure you check the rate when querying thresholds in modes (e.g., if var.rate < 0 and var.value <= target_floor) to avoid zero-tick ping-pong deadlocks when surging.

Zeroing Rates: You don't need to manually reset Level rates to zero every cycle. The DRSEngine zeroes them automatically before update_rates().

6. API Reference: Core Classes
Module Topology
Module: The semantic component base class.

variables(): Recursively yields all owned Variables and nested Variables.

modules(): Recursively yields this Module and all nested Modules.

named_modules(): Recursively yields PyTorch-style dotted module paths.

Deprecated compatibility topology: drs.network.Network, Node, and Edge remain importable for old graph-based models, but emit DeprecationWarning when instantiated.

Variables (drs.variables)
drs.Variable(name, initial_value, rate): The continuous base class. Includes directional threshold triggers.

drs.Level: Accumulates or depletes (automatically managed inside Nodes).

drs.State: Represents discrete categories (like Modes). Time-stepping ignores its rates, but Telemetry tracks its changes.

Simulation Loop (drs.engine & drs.module)
drs.Module: The base class for logic components (Controllers, overall Models).

DRSEngine(model): The runner class. Handles calculating dt and advancing time safely without breaching boundaries.
