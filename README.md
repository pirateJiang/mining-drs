# Mining-DRS: Discrete Rate Simulation Framework

Welcome to **Mining-DRS**! This library is a Python-based, object-oriented framework for building **Discrete Rate Simulations (DRS)**, with a focus on mining operations.

If you know nothing about mining, nothing about DRS, or nothing about this system, you are in the right place. This README will guide you from ground zero to building your own complex simulations.

---

## 1. Core Concepts Explained

### What is Mining (in this context)?
In this simulation framework, "mining" refers to the continuous process of extracting material from the earth and managing it. Specifically, we model:
- **Extraction**: Digging up "parcels" of rock.
- **Blending**: Ore often comes in different types or grades (e.g., Ore 1, Ore 2). The mine must blend them.
- **Stockpiles**: Mined ore is placed into stockpiles. If a stockpile gets too full or too empty, the mine must change its operational strategy (its "Mode").
- **Milling/Processing**: The plant consumes ore from the stockpiles at specific rates.
The goal of a mining simulation is often to evaluate if a specific control strategy can keep the plant running smoothly without emptying critical stockpiles.

### What is DRS (Discrete Rate Simulation)?
In traditional fixed-step simulations, time moves forward in small, fixed chunks (e.g., 1 second, 1 hour). This can be slow and sometimes misses exact threshold crossings.

**Discrete Rate Simulation (DRS)** operates differently:
1. Variables change continuously over time at a constant **rate**.
2. Variables have **thresholds** (upper and lower bounds).
3. The simulation calculates exactly **when** the next variable will hit its threshold.
4. Time "jumps" discretely to that exact moment.
5. At that moment, a **discrete event** occurs: rates might change, or the system might switch to a new operational mode.

This hybrid approach makes DRS perfectly suited for modeling continuous flows (like ore processing) governed by discrete control logic (like turning a machine on or off).

---

## 2. System Architecture: The `drs` API

The architecture of Mining-DRS is heavily inspired by PyTorch. Everything is organized into a tree of **Modules**, which contain **Variables**.

### The Main Components

- **`drs.Variable` / `drs.Level` / `drs.Timer`**: The core building blocks. These are quantities that change over time based on a `rate`.
- **`drs.State`**: A discrete variable (like an Enum) that represents the current mode of operation. It does not change continuously over time.
- **`drs.Module`**: The base class for your simulation components (e.g., a `MinePlant` or a `MineController`). Modules automatically register any variables or sub-modules assigned to them, just like `nn.Module` in PyTorch.
- **`DRSEngine`**: The "runner." It takes your root module, calculates time jumps, advances time, and triggers transitions.
- **`StateMachine`**: A command-pattern registry used to define what happens when a variable hits a threshold (e.g., "When Ore Stock hits 0, transition to SURGING mode").
- **`Telemetry`**: A built-in tracker that automatically records the value of all variables at every time step, allowing you to easily export the history to a Pandas DataFrame for plotting.

### The PyTorch $\rightarrow$ DRS Dictionary

Since the architecture is heavily inspired by PyTorch, you can map concepts directly:

- `nn.Module` $\rightarrow$ `drs.Module` (Your physical components)
- `nn.Conv2d` / `nn.Linear` $\rightarrow$ `drs.Level` / `drs.Timer` / `drs.State` (Generic building blocks that you piece together to build any physical system, just like neural network layers)
- `nn.Parameter` / `Tensor` $\rightarrow$ `drs.Variable` (The underlying tensors holding your values)
- `model.forward()` $\rightarrow$ `model.update_rates()` (Calculating the continuous dynamics based on the current state)
- `torch.optim.Optimizer` $\rightarrow$ `OperatingMode` (Applying specific rules/updates to the state)
- `DataLoader` / `Dataset` $\rightarrow$ `BaseOreGenerator` / `OreParcel` (Feeding data/geology to the plant)
- `Trainer` / `Training Loop` $\rightarrow$ `DRSEngine` (Advancing time/epochs)
- `TensorBoard` $\rightarrow$ `Telemetry` (Logging)

### Parallels to Reinforcement Learning (MDP / Gym Env)

The DRS framework maps naturally to a Markov Decision Process (MDP) or an OpenAI Gym Environment, making it highly suitable for Reinforcement Learning:

- **State ($S$)**: The values of your `drs.Variable`s (continuous state like stockpile levels, timers) and `drs.State`s (discrete states like current modes).
- **Action ($A$)**: The discrete mode switches or control decisions commanded by the controller/agent (e.g., switching from `MODE_A` to `MODE_B`).
- **Environment Dynamics / Transition ($P$)**: Handled by the `DRSEngine` advancing time to the next critical event, guided by the continuous derivatives defined in `update_rates()`.
- **`env.step(action)`**: Setting a new operational mode and allowing the `DRSEngine` to simulate until the next threshold is hit or a time horizon is reached.
- **Reward ($R$)**: Can be calculated during or after a step based on the simulation state or `Telemetry` data (e.g., rewarding throughput, penalizing empty stockpiles or excessive mode switching).

---

## 3. How the Engine Works (The Simulation Loop)

When you call `engine.run()`, the `DRSEngine` enters a loop:

1. **Check Termination**: Did we hit `max_time`, or did the module's `is_terminating_condition_met()` return True? If so, stop.
2. **Update Rates**: The engine calls `module.zero_rates()` to clear old data, then calls your `module.update_rates()`. This is where you set the current `rate` and `thresholds` for all variables based on the current state.
3. **Calculate Time Step (`dt`)**: The engine looks at all variables, their current values, rates, and thresholds, and determines the exact time (`dt`) until the closest threshold is hit.
4. **Advance Time**: Time jumps forward by `dt`. All variables update their values (`value += rate * dt`).
5. **Check Transitions**: The engine tells the module which variable triggered the event. The module calls `check_transitions()` to potentially change modes (states) based on this trigger.
6. **Record Statistics**: The `Telemetry` system takes a snapshot of all variables.

---

## 4. How to Build a Simulator (Step-by-Step)

Here is the standard workflow and best practice for creating a simulator using this framework.

### Step 1: Define Your Modes
Subclass `OperatingMode` to represent the discrete operational states of your system. You define the physics (how rates change) and preemption rules (when to switch modes) here.

```python
from drs.modes import OperatingMode, RequireDecision

class NormalOperation(OperatingMode):
    @property
    def id(self) -> int: return 0

    @property
    def name(self) -> str: return "NORMAL"
    
    def is_valid_start(self, model) -> bool:
        return True

    def apply_dynamics(self, model):
        # Apply the physics for this specific mode
        model.plant.ore_stock.rate = -100.0

    def check_end_conditions(self, model):
        # E.g., if stockpile runs out, ask the controller what to do
        if model.plant.ore_stock.value <= 0:
            return RequireDecision()
        return None
```

### Step 2: Create the Physical Plant
Subclass `drs.Module`. Define the physical variables (Levels) in `__init__`. Override `update_rates()` to define any global, unconditional rules that always apply. For external data, pass in an iterable `loader` (similar to a `DataLoader` feeding `OreParcel`s) and let the Plant manage its own transitions to load the next batch when thresholds are hit.

```python
from drs import drs
from drs.data import BaseOreGenerator, OreParcel

class GenerativeOreLoader(BaseOreGenerator):
    def __iter__(self): return self
    def __next__(self) -> OreParcel:
        return OreParcel(mass=40000.0, grade=100.0)

class MinePlant(drs.Module):
    def __init__(self, loader: BaseOreGenerator):
        super().__init__()
        self.loader = iter(loader)
        self.current_parcel_mass = drs.State("parcel_mass", 0.0)
        self.ore_extraction = drs.Level("OreExtraction", initial_value=0.0)
        self._load_next_batch()

    def _load_next_batch(self):
        try:
            parcel = next(self.loader)
            self.current_parcel_mass.value = parcel.mass
        except StopIteration:
            pass

    def update_rates(self):
        # Global limits that always apply
        self.ore_extraction.upper_threshold = self.current_parcel_mass.value

    def check_transitions(self, trigger_var=None, is_upper=True):
        # Plant handles its own physics transitions
        if trigger_var == self.ore_extraction and is_upper:
            self._load_next_batch()
            self.ore_extraction.value = 0.0
            self.ore_extraction.upper_threshold = self.current_parcel_mass.value
```

### Step 3: Create the Controller
Subclass `drs.Module`. Define control variables (Timers, States) and handle mode switching.

```python
class MineController(drs.Module):
    def __init__(self, plant: MinePlant):
        super().__init__()
        self.plant = plant
        self.current_mode = drs.State("current_mode", NormalOperation())
        self.timer = drs.Timer("CampaignTimer", initial_value=0.0)

    def update_rates(self):
        # Timers tick up naturally
        self.timer.rate = 1.0
        # The mode dictates the rest of the physics!
        self.current_mode.value.apply_dynamics(self.parent)

    def check_transitions(self, trigger_var=None, is_upper=True):
        # Ask the mode if its end conditions are met
        next_mode = self.current_mode.value.check_end_conditions(self.parent)
        
        from drs.modes import RequireDecision
        if isinstance(next_mode, RequireDecision):
            # Controller fallback logic
            next_mode = ShutdownMode() 
            
        if next_mode:
            self.current_mode.value = next_mode
```

### Step 4: Combine into a Root Model
Create a master module that contains both the plant and controller. Initialize `Telemetry`.

```python
from drs.telemetry import Telemetry

class ExampleMineModel(drs.Module):
    def __init__(self):
        super().__init__()
        self.loader = GenerativeOreLoader()
        self.plant = MinePlant(self.loader)
        self.controller = MineController(self.plant)
        
        self.telemetry = Telemetry(self) # Auto-tracks all variables
        # You can register custom metrics that run on every snapshot
        self.telemetry.register_metric(
            "TimerValue",
            lambda t, m, s, h: m.controller.timer.value
        )

    def update_rates(self):
        # Delegate down the tree
        self.plant.update_rates()
        self.controller.update_rates()

    def check_transitions(self, trigger_var=None, is_upper=True):
        self.plant.check_transitions(trigger_var, is_upper)
        self.controller.check_transitions(trigger_var, is_upper)
```

### Step 5: Run the Simulation & Plot
```python
from drs import DRSEngine
from drs.plot import build_dashboard, plot_time_series

sim = ExampleMineModel()
engine = DRSEngine(sim)
engine.run(max_time=365.0) # Run for 365 simulated days

df = sim.telemetry.to_dataframe()

# Create visualisations easily
configs = [
    {
        "func": plot_time_series,
        "kwargs": {"y_columns": ["OreStock_Level"], "title": "Stockpile Level"}
    }
]
dashboard = build_dashboard(df, configs, title="Simulation Dashboard")
dashboard.savefig("results.png")
```

---

## 5. Conventions & Best Practices

1. **Separation of Concerns**: Always separate the physical system (`MinePlant`) from the logic system (`MineController`).
2. **`OperatingMode` Object Orientation**: Keep mode-specific transition logic and rate assignments contained within their respective `OperatingMode` classes. Keep global rules in the Plant.
3. **Threshold Triggers**: When a threshold is hit, the engine triggers `check_transitions(trigger_var)`. Use `trigger_var` to identify what caused the event if multiple thresholds might fire at once.
4. **Side Effects**: If an event (like a parcel finishing) shouldn't change the mode but needs to trigger a side-effect (like generating a new parcel), intercept it at the top of your controller's `check_transitions` function.
5. **Zeroing Rates**: You don't need to manually reset rates to zero every cycle. The `DRSEngine` calls `zero_rates()` on all variables before calling `update_rates()`, ensuring that un-updated variables default to a rate of 0 and infinite thresholds.

---

## 6. API Reference: Functions and Classes

### Variables (`drs.variables`)
* **`drs.Variable(name, initial_value, rate)`**: The base class.
  * `.value`: Current continuous value.
  * `.rate`: How fast the value changes per unit of time.
  * `.upper_threshold` / `.lower_threshold`: Limits. If reached, an event triggers.
  * `.upper_bound` / `.lower_bound`: Properties used as triggers when registering transitions.
* **`drs.Level(name, initial_value, rate)`**: Semantically represents a physical quantity that accumulates or depletes (like a stockpile). Inherits from `Variable`.
* **`drs.Timer(name, initial_value, rate=1.0)`**: Semantically represents a clock or stopwatch. Inherits from `Level`. Contains a `.reset()` method to set the value back to 0.0.
* **`drs.State(name, initial_value)`**: Represents discrete categories (like Enums, Modes). The engine ignores its rates for time-stepping, but Telemetry records its state changes.

### Module (`drs.module`)
* **`drs.Module`**: The base class for all components.
  * `__init__()`: Always call `super().__init__()` first. Assign variables as attributes here.
  * `variables()`: Returns a generator yielding all `Variable` objects in this module and its sub-modules.
  * `update_rates()`: **Must Override**. Define the continuous dynamics here.
  * `check_transitions(trigger_var, is_upper)`: **Override**. Handle state changes here when a threshold is hit.
  * `initialize_state()`: **Override optionally**. Set up initial conditions before simulation starts.
  * `is_terminating_condition_met()`: **Override optionally**. Return `True` to stop the simulation dynamically.

### Operating Modes (`drs.modes`)
* **`OperatingMode`**: Abstract base class for defining operational states.
  * `apply_dynamics(model)`: Set rates and thresholds specific to this mode.
  * `check_end_conditions(model)`: Check if the state forces a transition. Return the next `OperatingMode`, `RequireDecision()`, or `None`.
  * `is_valid_start(model)`: Returns boolean indicating if the mode is valid under the current state.
* **`RequireDecision`**: A signal flag returned by `check_end_conditions` indicating the Controller should take over transition logic.

### Engine (`drs.engine`)
* **`DRSEngine(model)`**: The runner class.
  * `run(max_time=None)`: Starts the simulation loop. Runs until `max_time` is reached or the model dictates termination.

### Telemetry (`drs.telemetry`)
* **`Telemetry(model)`**: Tracks variables automatically.
  * `to_dataframe()`: Returns a Pandas `DataFrame` containing the time-series history of the simulation.
  * `register_metric(name, calc_fn)`: Register a custom calculation evaluated at every step.

### Plotting (`drs.plot`)
* **`build_dashboard(df, plot_configs, ...)`**: Generates a composite figure with multiple subplots.
* **`plot_time_series`, `plot_ore_with_modes`, `plot_mode_distribution`, etc.**: Individual plotting functions designed for DRS telemetries.
