# ADR 0003: The Simulation Loop and Engine Tick

## Status
Accepted

## Context
In Arena DRS simulations, flow logic is typically divided into "5 Islands", often represented as separate flowcharts handling initialization, calculation of time-to-next-threshold (dt), state updates, threshold scanning/triggering, and statistical recordings. In addition, a "Hold" block is frequently used to pause simulation progress until conditions are met. Porting this logic directly into Python can result in confusing asynchronous execution and unstructured procedural code. 

## Decision
We abstract the "5 Islands" approach into a standardized `tick()` simulation loop within an explicit `DRSEngine` base class. 
The simulation sequence resolves asynchronously looping issues and "Hold" blocks:
1. `initialize_state()` (Island 1)
2. A `while` loop checks `not is_terminating_condition_met()` to replace "Hold" blocks explicitly.
3. `calculate_time_to_next_threshold()` (Island 2)
4. `advance_time(dt)` (Island 3)
5. `check_and_trigger_thresholds()` (Island 4)
6. `record_statistics()` (Island 5)

## Consequences
- **Pros:**
  - Standardized structure for all derived models (e.g., `MiningDRSEngine`).
  - No need for complex "Hold" mechanisms; conditions are checked natively in the `tick` and `calculate_time_to_next_threshold` processes.
  - Transparent execution sequence makes debugging and maintaining time logic simpler.
- **Cons:**
  - Derived classes must implement abstract methods correctly for the loop to behave synchronously.
