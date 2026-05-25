# ADR 0007: Telemetry System and Output Statistics

## Status
Accepted

## Context
In previous simulation setups, output statistics and specific variable trackers had to be manually recorded and wired to the end of the simulation loop explicitly. Because many statistics are relevant to all simulation models, manually adding export hooks for every variable was tedious and prone to errors.

## Decision
We introduce an automated `Telemetry` system that hooks into the `DRSEngine` simulation loop.
- Because all variables (Timers, Levels, Trackers) are instantiated as objects (ADR 0001), the `Telemetry` class can dynamically iterate over the engine's list of `variables` and capture a full snapshot of the simulation state.
- Snapshots are taken at intervals (usually every tick/event), capturing the state as a list of dictionaries.
- Data export is streamlined through a `to_dataframe()` method which seamlessly drops the entire history into a `pandas.DataFrame` for downstream analytics and beautiful plotting capabilities.

## Consequences
- **Pros:**
  - Automatic collection of all tracked variables reduces boilerplate code in the simulation engine.
  - Generates analysis-ready DataFrames instantly.
  - Supports detailed time-series plotting of the system state immediately after run completion.
- **Cons:**
  - Recording the state every tick consumes memory. For extremely long-running simulations with high granularity, snapshotting might need to be downsampled (e.g., every N ticks or every M seconds) to prevent `MemoryError`s.
