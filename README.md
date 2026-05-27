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
Create an `Enum` representing the discrete operational states of your system.
```python
from enum import Enum

class MineMode(Enum):
    MODE_A = "Normal Operation"
    MODE_B = "Recovery Mode"
    SHUTDOWN = "Maintenance"
```

### Step 2: Create the Physical Plant
Subclass `drs.Module`. Define the physical variables (Levels) in `__init__`. Override `update_rates(mode)` to define how rates change based on the current mode. Set `upper_threshold` or `lower_threshold` to limit these levels.

```python
from mining_drs import drs

class MinePlant(drs.Module):
    def __init__(self):
        super().__init__()
        self.ore_stock = drs.Level("OreStock", initial_value=50000.0)

    def update_rates(self, mode: MineMode):
        # Set thresholds
        self.ore_stock.upper_threshold = 100000.0
        self.ore_stock.lower_threshold = 0.0
        
        # Set continuous dynamics based on the mode
        if mode == MineMode.MODE_A:
            self.ore_stock.rate = -100.0 # Depleting slowly
        elif mode == MineMode.MODE_B:
            self.ore_stock.rate = 50.0   # Replenishing
        elif mode == MineMode.SHUTDOWN:
            self.ore_stock.rate = 0.0    # Stopped
```

### Step 3: Create the Controller
Subclass `drs.Module`. Define control variables (Timers, States) and manage the `StateMachine`.

```python
from mining_drs.modes import StateMachine

class MineController(drs.Module):
    def __init__(self, plant: MinePlant):
        super().__init__()
        self.plant = plant
        self.current_mode = drs.State("current_mode", MineMode.MODE_A)
        self.timer = drs.Timer("CampaignTimer")
        
        self.registry = StateMachine()
        self._setup_transitions()

    def _setup_transitions(self):
        # When OreStock hits 0, go to MODE_B
        self.registry.register_transition(
            source=MineMode.MODE_A,
            trigger=self.plant.ore_stock.lower_bound,
            target=MineMode.MODE_B
        )
        # When CampaignTimer hits its limit, SHUTDOWN
        self.registry.register_transition(
            source=MineMode.MODE_B,
            trigger=self.timer.upper_bound,
            target=MineMode.SHUTDOWN
        )

    def update_rates(self):
        # Timers tick up at rate 1.0
        self.timer.rate = 1.0
        self.timer.upper_threshold = 100.0 # 100 days until shutdown

    def check_transitions(self, trigger_var=None, is_upper=True):
        # Ask the state machine what the next mode is based on what triggered
        next_mode = self.registry.get_next_mode(self.current_mode.value, trigger_var, is_upper)
        if next_mode:
            self.current_mode.value = next_mode
```

### Step 4: Combine into a Root Model
Create a master module that contains both the plant and controller. Initialize `Telemetry`.

```python
from mining_drs.telemetry import Telemetry

class ExampleMineModel(drs.Module):
    def __init__(self):
        super().__init__()
        self.plant = MinePlant()
        self.controller = MineController(self.plant)
        self.telemetry = Telemetry(self) # Auto-tracks all variables

    def update_rates(self):
        # Delegate down the tree
        self.controller.update_rates()
        self.plant.update_rates(self.controller.current_mode.value)

    def check_transitions(self, trigger_var=None, is_upper=True):
        self.controller.check_transitions(trigger_var, is_upper)
```

### Step 5: Run the Simulation
```python
from mining_drs import DRSEngine

sim = ExampleMineModel()
engine = DRSEngine(sim)
engine.run(max_time=365.0) # Run for 365 simulated days

# Export to Pandas and plot!
df = sim.telemetry.to_dataframe()
print(df.head())
```

---

## 5. Conventions & Best Practices

1. **Separation of Concerns**: Always separate the physical system (`MinePlant`) from the logic system (`MineController`).
2. **Continuous vs Discrete**: 
   - Use `update_rates()` strictly for assigning continuous `rate` and `threshold` values.
   - Use `check_transitions()` (via the `StateMachine` registry) strictly for handling discrete mode changes or instant state resets.
3. **Threshold Triggers**: When registering transitions in the StateMachine, use the `.upper_bound` and `.lower_bound` properties of a variable as the `trigger`. (e.g. `trigger=plant.ore_stock.lower_bound`).
4. **Side Effects**: If a transition shouldn't change the mode but needs to trigger a side-effect (like generating a new parcel of ore), pass a python function as the `target` in `register_transition`. Ensure the function returns `None`.
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
* **`drs.State(name, initial_value)`**: Represents discrete categories (like Enums). The engine ignores its rates for time-stepping, but Telemetry records its state changes.

### Module (`drs.module`)
* **`drs.Module`**: The base class for all components.
  * `__init__()`: Always call `super().__init__()` first. Assign variables as attributes here.
  * `variables()`: Returns a generator yielding all `Variable` objects in this module and its sub-modules.
  * `update_rates()`: **Must Override**. Define the continuous dynamics here.
  * `check_transitions(trigger_var, is_upper)`: **Override**. Handle state changes here when a threshold is hit.
  * `initialize_state()`: **Override optionally**. Set up initial conditions before simulation starts.
  * `is_terminating_condition_met()`: **Override optionally**. Return `True` to stop the simulation dynamically.

### StateMachine (`drs.modes`)
* **`StateMachine`**: A registry for transitions.
  * `register_transition(source, trigger, target)`: Binds a trigger (e.g. a timer hitting its upper bound) to a target (a new Mode `Enum`, or a callable function).
  * `get_next_mode(current_mode, trigger, is_upper)`: Evaluates the registry to find if a transition should occur.

### Engine (`drs.engine`)
* **`DRSEngine(model)`**: The runner class.
  * `run(max_time=None)`: Starts the simulation loop. Runs until `max_time` is reached or the model dictates termination.

### Telemetry (`drs.telemetry`)
* **`Telemetry(model)`**: Tracks variables automatically.
  * `snapshot(current_time)`: Called internally by the Engine to record data.
  * `to_dataframe()`: Returns a Pandas `DataFrame` containing the time-series history of the simulation. Perfect for Matplotlib or Seaborn.
  * `register_metric(name, calc_fn)`: Allows you to register a custom calculation (like Net Present Value) that gets evaluated and recorded at every time step based on the simulation state.
