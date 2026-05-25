# ADR 0001: Use Object-Oriented New Types for Variables

## Status
Accepted

## Context
The previous "arena" method used 2D matrices and 1D vectors to hold state. This is an anti-pattern in Python where semantic representation of the domain is preferred. Specifically, separating "Levels" from "Timers" while keeping them fundamentally similar was difficult with raw matrices, leading to manual array assignments like `drs_Level(1) = ...`. Furthermore, some variables are just output statistics (trackers) that do not affect simulation logic but still need to record data.

## Decision
We will use object-oriented explicit classes to represent different variable types in the simulation instead of strings or raw matrices:
- `Variable`: The base class containing the name and value.
- `Level`: Inherits from `Variable`, adds a `rate` property, and an `update(dt)` method to increment the value over time.
- `Timer`: Inherits from `Level`, representing a level where the rate is typically constant, and includes a `reset()` method.
- `Tracker`: Inherits from `Variable`, used for output statistics that do not affect simulation logic.

## Consequences
- **Pros:**
  - Semantic domain representation.
  - Updating levels happens automatically in the engine (e.g., `for level in self.levels: level.update(dt)`).
  - Removing manual array assignments.
  - Easy extension for new variable types.
- **Cons:**
  - Slightly more overhead than raw matrices, but likely negligible for the simulation scale and greatly improves code maintainability.
