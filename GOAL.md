# DRS Framework — Goals & Design Notes

## Vision

- General DRS, not just mining
- Components in `drs/` are not mining-specific
- Efficient — run FAST
- Python first: simple, fast, easy to read, feels like PyTorch
- Secondarily: drag-and-drop Visual approach like Arena, with Python ↔ Visual round-trip
- The PyTorch of DRS
- Bridge between programmers and non-programmers (mining engineers, etc.)
- Improve on Arena by supporting DRS natively — semantic modules (Plant, Fleet, Mine, Stockpile) instead of pointer entities + assigns
- Hierarchical modules: zoom into a Fleet to see individual trucks as sub-modules
- Fail fast! Errors should be caught early with clear messages
- Based on Navarra's work — operating modes are first-class

---

## Status Overview

### ✅ Completed (Phase 1 & 2)

| Area | What |
|------|------|
| **`__setattr__` auto-registration** | `Module.__setattr__` auto-registers Variables, Levels, Timers, sub-Modules (like PyTorch `nn.Module`). No manual `register_buffer`/`add_module` calls needed. |
| **Expression dual-mode system** | Operator overloading (`__add__`, `__sub__`, `__gt__`, etc.) builds Expression ASTs during tracing; evaluates numerically during simulation. See `drs/variables.py`. |
| **ExecutionContext** | Thread-local stack tracking which module is currently executing via `Module.__call__` push/pop. Enables implicit read/write dependency tracing. |
| **Fail-fast guards** | Illegal cross-module mutations raise `RuntimeError`. `Expression.__bool__` raises `TypeError` (prevents silent truthiness bugs). |
| **Level.rate tuple setter** | `level.rate = (value, lower, upper)` convenience shorthand. |
| **Configurable DRSEngine** | `max_step_size`, `max_deadlock_steps` parameters. |
| **Engine exception safety** | `try/finally` around context push/pop ensures stack integrity even on exception. |
| **Dead code removed** | `Signal` removed from `drs/data.py`. `CoreDRSConfig` deleted. Old import-style `ModeA`/`ModeB`/etc. classes replaced. |
| **Operating modes** | Single `OperatingMode` class + `MODES` dict singleton registry (13 old classes → 1 class + 1 dict). `RequireDecision` sentinel/exception for controller-engine coordination. |
| **Controller timer map** | 120-line `_update_timers` if-elif chain → 8-line dict-driven lookup on `_TIMER_MAP`. Subclasses extend via `_TIMER_MAP = {**Base._TIMER_MAP, ...}`. |
| **Clean controller_decision** | Extracted `_choose_next_campaign_mode()` — CyanidationController overrides just this method for Stage 2 (C/D) logic instead of duplicating the entire decision method. |
| **RL environment** | `RL_MineController` uses `RequireDecision` exception to pause engine for RL agent input. Verified working. |
| **Blending example** | Verified end-to-end: all modes (A, B, contingencies, surging, shutdown) transition correctly through full campaign cycles. |
| **Tests updated** | Integration tests use `controller.forward()` directly and correct attribute paths. |

### 🔄 In Progress / Partially Done

| Item | Notes |
|------|-------|
| **Mass balance automation** (`supply_chain.py`) | Plant still manually sums child stockpile rates. Not yet automated. |
| **Generalized sensor system** | Currently mining-specific (`BaseSensorNetwork`, `ConcentratorSensorNetwork`). Not abstracted for general DRS. |

### ❌ Not Yet Started

| Item | Priority |
|------|----------|
| Visual drag-and-drop system (Arena-like) | **HIGH** |
| `drs.compile()` — AST optimization for Monte Carlo | MEDIUM |
| Parallel Monte Carlo execution | MEDIUM |
| Stochastic drive times / fleet delays | LOW |
| Generalized DataGenerator / DataLoader | LOW |
| Topological order warning | LOW |

---

## Resolved Design Decisions

These are goals from the original vision that are now implemented and considered stable.

### 1. `__setattr__` Auto-Registration (like PyTorch)

Assigning a `drs.Variable`, `drs.Level`, `drs.Timer`, or sub-`drs.Module` via `self.x = ...` in `__init__` automatically registers it as a child. The `_owner` reference is set so the framework knows which module owns each variable. No manual `register_buffer` or `add_module` calls required.

**Status:** ✅ Implemented in `drs/module.py`.

### 2. Implicit Graph Emergence

Graph nodes and connections emerge from behavior, not from explicit registration. Something has to happen (read, write, or compute) for a connection to be recorded. Explicit connections are avoided because they may not match logic, add boilerplate, and are more work.

**Status:** ✅ Implemented via `_record_incoming_edge()` in `Module` + ExecutionContext tracking in `Variable`.

### 3. Expression Dual-Mode (AST + Evaluation)

Operator overloading returns `Expression` AST nodes during tracing, which are evaluated recursively during simulation. The `Variable.value` property checks if it holds an `Expression` and evaluates it on access.

**Status:** ✅ Implemented in `drs/variables.py`.

### 4. Fail-Fast Philosophy

- Illegal cross-module mutations → `RuntimeError` with descriptive message
- `Expression.__bool__` → `TypeError` (no silent truthiness)
- Only `Level` has `.rate` — `Variable` raises `AttributeError` on `.rate = x`

**Status:** ✅ Implemented.

### 5. Operating Modes as First-Class Citizens

Based on Navarra's work, operating modes are central. Single `OperatingMode` class with `name`, `id`, `is_valid_start()`, `get_target_rates()`, `check_end_conditions()`. Singleton registry via `MODES` dict.

**Status:** ✅ Implemented in `examples/mining/components/modes.py`.

### 6. DRSEngine Resets Rates Each Tick

Before calling `model.forward()`, the engine zeros out all rate ASTs. This is the standard DRS approach and is currently working.

**Status:** ✅ Implemented.

### 7. Unification of Logic into `forward()` (update_rates deprecated)

Because the engine uses an implicit graph and traces ASTs dynamically, the traditional separation of "calculating rates" and "stepping state" is obsolete. All physical routing, state assignments, and mode transitions are unified under the `forward()` pass. `update_rates()` is removed to eliminate boilerplate and enforce PyTorch-like encapsulation.

**Status:** ✅ Implemented. `drs.Module` has `forward()`, not `update_rates()`. The engine calls `forward()` once per tick to compute all rates, then integrates levels.

### 8. Controller Uses `RequireDecision` Pattern

`OperatingMode.check_end_conditions()` returns `RequireDecision()` (sentinel) when the engine needs external input. The RL controller raises `RequireDecision` as an actual exception to pause the engine. The engine handles both cases safely.

**Status:** ✅ Implemented.

---

## Core Implementation Architecture

### 1. The "Rule of Ownership" (In-Place Mutation Guardrail)

To prevent users from silently destroying the visual graph by doing `controller.mill.rate = 5`, the Variable setters must check the `ExecutionContext`. If the currently executing module is not the owner of the variable, it raises a `RuntimeError` forcing them to pass a `drs.Signal` instead.

```python
class Variable:
    @value.setter
    def value(self, val):
        current_actor = ExecutionContext.get_current()
        if current_actor is not None and current_actor is not self._owner:
            raise RuntimeError(
                f"'{current_actor.__class__.__name__}' attempted to mutate "
                f"'{self.name}' owned by '{self._owner.__class__.__name__}'. "
                f"Modules must communicate by passing Signals/Flows."
            )
        self._value = val
```

**Status:** ✅ Implemented in `drs/variables.py`.

### 2. The Engine Loop ($dt_{min}$ Integration)

The engine follows these exact steps each tick:

1. **Evaluate `forward()` passes** to get instantaneous rates from all modules.
2. **Iterate over all `drs.Level`s** to find the smallest time to a threshold ($dt_{min}$) — i.e., the earliest moment any level hits its upper or lower bound.
3. **Apply `level.update(dt_min)` globally** — advance all levels by the same $dt_{min}$.
4. **Trigger state/mode transitions** — check if any threshold was crossed and activate new operating modes for the next tick.

**Status:** ✅ Implemented in `drs/engine.py`. `DRSEngine.run()` follows this exact loop.

### 3. Reproducible Stochasticity (Monte Carlo Goal)

Global `random` or `np.random` is banned. For parallel Monte Carlo execution to work correctly, the top-level module must accept an RNG seed and pass localized `RandomState` instances down to stochastic components (like `MineFace`).

```python
class BaseBlendingModel(drs.Module):
    def __init__(self, config, seed=None):
        self.rng = np.random.RandomState(seed)
        self.face1 = MineFace(rng=self.rng)
        self.face2 = MineFace(rng=self.rng)
```

This ensures each parallel replica produces an identical sequence given the same seed, enabling deterministic Monte Carlo.

**Status:** 🔄 Partially implemented. `StochasticFaciesGenerator` accepts a seed, but the pattern is not enforced across all stochastic components (fleet drive times, etc.).

### 4. The UI Blueprint Extraction (Symbolic "Dry Run")

Because the graph is built dynamically at Run-Time (which allows native Python `if`/`else` control flow), the framework needs a **Symbolic Trace** feature. This passes fake "Symbolic" signals through the system before the engine starts, exploring all `if`/`else` branches to emit a complete JSON Simulation IR. This JSON is what powers the Arena-like Drag-and-Drop UI.

Mechanics:
- A "tracing mode" in `ExecutionContext` where all `Variable` reads return symbolic `Expression` objects instead of raw values
- Operator overloads (`__gt__`, `__add__`, etc.) build ASTs AND log edges
- Branch exploration: when the trace hits `if stock_level > 200`, it forks — following both the True and False paths to capture the full decision tree
- Output: a JSON IR encoding all modules, variables, edges, and control-flow branches — the blueprint for the visual canvas

**Status:** ❌ Not implemented. The `Expression` AST system and `ExecutionContext` provide the foundation, but the symbolic trace pass and JSON IR emission do not exist yet.

---

## Unresolved Design Questions

### Group 1: Inter-Module Communication

This is the biggest unresolved design question. There are several competing approaches:

#### Approach A: Port-based (explicit InputPort/OutputPort)

```python
class Stockpile(drs.Module):
    def __init__(self):
        self.inflow = drs.InputPort()
        self.outflow = drs.OutputPort()
        self.level = drs.Level()
```

**Pros:** Explicit, type-safe, maps 1:1 to visual connections
**Cons:** Boilerplate, feels "un-PyTorchy", every class must define ports

#### Approach B: Functional `forward()` with Signal/Flow Passing

```python
def forward(self, inflow_signal, requested_outflow):
    actual_outflow = min(self.level.value / dt, requested_outflow.value)
    self.level.rate = inflow_signal.value - actual_outflow
    return drs.Signal(value=actual_outflow, source_module=self)
```

**Pros:** Clean data flow, edges are obvious from call graph, natural for visualization
**Cons:** Sometimes a module returns something, sometimes it doesn't (confusing). What does `Module.__call__` return for a controller? A sensor? What happens to modules that only set rates internally?

#### Approach C: Bind Method

```python
self.plant.inflow.bind(self.fleet.outflow)
```

**Pros:** Explicit, no heuristics needed
**Cons:** Extra manual step, dynamic binding may be complex

#### Approach D: Implicit via ExecutionContext + `__setattr__` (Current System)

The current approach: modules hold references to each other and set rates directly. ExecutionContext tracks who's doing what.

```python
class ModeController(drs.Module):
    def forward(self):
        if self.stockpile.level > 200:
            self.mill.capacity_target = 6000
```

**Pros:** Maximum flexibility, most PyTorch-like
**Cons:** Hard to determine direction of flow, hard to enforce discipline, graph tracing is implicit and fragile

#### Sub-questions:

- **Signal vs Flow vs dict vs RateVector?** Generic `drs.Signal` with `attributes` dict? A `drs.Flow` dataclass? Dictionary of rates? `VectorLevel`/`VectorRate` for tracking individual component rates explicitly?
- **Everything as a node vs two systems?** Should controllers and sensors be graph nodes (everything is a node) or kept separate from the physical flow network? A separate network for physical stuff creates two systems to track.
- **Is a Signal the same as a Flow?** A `drs.Flow` is "just an ephemeral dataclass that carries the rates between modules during a single execution tick." Is this different from our existing `Variable` class?

**Key tension:** The explicit connector approach (Ports) is robust and good for visualization but adds boilerplate. The implicit approach (current) is flexible and PyTorch-like but makes visualization and correctness harder.

---

### Group 2: Tracing Reads of External Variables

When a module reads a variable owned by another module (e.g., controller reading stockpile level), how do we capture this as a graph edge?

#### Approach A: Pass variables as `forward()` arguments

```python
class ModeController(drs.Module):
    def forward(self, stock_level: drs.Variable):
        if stock_level > 200:
            return drs.Flow(command="MODE_A")
```

**Problem:** Forces users to pass every dependency as an argument — breaks OO encapsulation, not PyTorch-like.

#### Approach B: ExecutionContext read hooks (recommended)

The same `ExecutionContext` used for mutation guards can also log reads:

```python
class Variable:
    @property
    def value(self):
        self._record_read_dependency()  # <-- logs: owner --> current_actor
        return self._value
```

When `ModeController` evaluates `self.stockpile.level > 200`, the `__gt__` overload calls `_record_read_dependency()`. The framework silently logs "Stockpile → ModeController".

**Current status:** Partially implemented. `_record_incoming_edge` exists but the automatic read-hook in every `__gt__`/`value` getter is not yet complete for all operator overloads.

#### Approach C: `__set__` descriptor override

Intercepting Python's descriptor protocol to track assignments. Less explored.

---

### Group 3: Dynamic Control Flow (if/else with Variables)

The classic PyTorch/JAX trap: Python `if stock_level > 200` evaluates `>` which returns an `Expression` AST, and Python can't cast `Expression` to `bool`.

#### Current solution: `Expression.__bool__` raises `TypeError` (fail-fast)

Users must explicitly use `.value`: `if stock_level.value > 200`.

#### Competing approaches:

**A: PyTorch Way (Dynamic)**
Let `stock_level.value > 200` evaluate to a raw boolean. Re-trace the graph on every tick. Easier to code, slightly slower.

**B: JAX Way (Symbolic)**
Implement `drs.Where` or `drs.Switch` that builds conditions into the AST:
```python
self.mill_rate = drs.Where(stock_level > 200, 6000, 3900)
```
Faster, easier to visualize, but less intuitive for Python users.

**Lean:** Currently partial toward JAX approach but not sold.

---

### Group 4: Variable / Data Type System

#### Current types:
- `Variable` — general-purpose state
- `Level` — has `.rate`, integrates over `dt` (continuous flow)
- `Timer` — like Level, monotonically increasing
- `Expression` — AST node returned by operator overloads
- `State` — Categorical (not yet implemented)

#### Competing formulations:

**A: Multiple types (current)** — Variable, Level, Timer, Auxiliary, State
- Problem: Variable and Auxiliary are semantically too similar

**B: Minimal — just Variable and Level**
- Rates, constants, states all as Variable
- Only Level has `.rate` (fail-fast: `Variable.rate = x` raises `AttributeError`)
- Add `drs.Flow` for inter-module messages
- `Variable.value` evaluates Expression AST on access

**C: Two families — Continuous (Variable, Level, Timer) and Categorical (State)**
- Streamline existing implementation
- Remove `@property` interceptions where not needed
- Only Level has rates
- `Variable.value` auto-evaluates AST

---

### Group 5: Container Modules (Top-Level vs Visual Nodes)

The top-level model (e.g., `ConcentratorModel`) is a container, not a graph node. Other modules may also be containers.

**Problem:** How to distinguish containers from leaf nodes without an `is_container` flag? A flag adds boilerplate and is "un-PyTorchy." Easy to forget.

**Options:**
- Heuristic: modules containing sub-modules but no variables are containers
- Explicit: `is_container` flag (undesirable)
- Implicit: container detection via graph topology

---

## Performance & Future Work

### AST Compilation (`drs.compile()`)

Currently each `Expression.evaluate()` recursively walks the AST tree. For Monte Carlo (10,000+ runs), this is slow.

**Planned fix:** `engine.compile()` walks ASTs and uses Python's `compile()` or NumPy ops to produce optimized bytecode.

### Parallel Monte Carlo Execution

Goal: efficient parallel execution for Monte Carlo simulation results.

### Topological Order Warning

Add a warning when execution order doesn't match topological order, which can lead to 1-tick delays.

---

## Visual System (Not Started)

This is the largest remaining goal. Requirements from the vision:

- Drag-and-drop interface like Arena
- Python ↔ Visual round-trip (build in visual, edit in Python, and back)
- Visual system represents how the system actually runs (visual debugging)
- See flow and different operating modes visually
- Visual levels of abstraction — zoom into a module to see its internals
- Create custom components visually (Stockpile class, ConcentratorPlant, etc.)
- Visual system should be usable by non-programmers (mining engineers)
- A non-programmer builds a simple version visually, hands off to programmer for RL/LP

---

## Mining-Specific / Example Improvements

### Mass Balance Automation
Currently the plant manually sums child stockpile rates. This should be automated — when you set the concentrator rate, the fleet rate should implicitly balance.

### Fleet Management Scenario (Navarra 2019, Fig 6)
Goals:
1. Increase time in Mode A, reduce contingencies
2. Keep ~60/40 Ore1/Ore2 stockpile ratio
3. Add stochastic drive times
4. Add conveyors, gradual parcel additions
5. Multiple muck sites with different distances and grades
6. Limited truck capacity

### Stochasticity
- Ore generation (done)
- Fleet drive times (not done)
- Other stochastic elements (not done)

### Sensors & Uncertainty
- True vs belief values
- Are sensors edges or nodes?
- Is this mining-specific or general DRS?

### Other Mining Goals
- Allow passing more than just mass (e.g., cyanide usage)
- Dynamic mass balance enforcement
- Bridge between Navarra and Ruossos
- SGS (Sublevel Stoping) support
- Custom metrics (NPV, etc.)
- Delays for operating changes, travel time
- OpenAI Gym for Mining Optimization — reusable benchmark scenarios

---

## Open Questions (Miscellaneous)

- Should we prevent incorrect edges/connections (e.g., mass flowing into grade)? Or does this add too much boilerplate?
- Can we generalize OreParcel as a `DataGenerator` / `DataLoader` (like PyTorch Dataset)?
- Do I want `rate = inflow - outflow` syntax? Is this nicer than the current approach?
- Is there a way to track data paths without modules returning data? (Currently rates update levels, which feels natural for DRS)
- What about JAX-like functional approach vs SystemC vs Modelica vs Arena? Pros and cons for DRS?

---

## Original "Current Plan" (from earlier goals)

1. ~~Data Types like Resource, Observation, Control~~ — replaced by Expression AST system
2. ~~Register children with `__setattr__`~~ — ✅ Done
3. ~~Graph nodes emerge from behaviour~~ — ✅ Done (ExecutionContext tracing)
4. ~~A `drs.Module` that represents a visual block~~ — ❌ Not started

---

*Last updated: June 2026*
