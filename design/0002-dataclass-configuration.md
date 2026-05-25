# ADR 0002: Dataclass-based Configuration Hierarchy

## Status
Accepted

## Context
When configuring the simulation, we need a clear distinction between generic parameters required for all DRS models and specific parameters used only in certain contexts (like Mining). The legacy or alternative approaches might use unstructured dictionaries or flat configuration objects with no default fallback mechanisms, which could lead to missing parameter errors at runtime rather than failing fast.

## Decision
We will use Python's `dataclasses` (specifically with inheritances) to manage parameters and configurations.
- `CoreDRSConfig`: Contains the base parameters common to all DRS models. 
- `MiningDRSConfig`: Inherits from `CoreDRSConfig` and adds mining-specific variables.
- We utilize `dataclass`'s built-in type hints and `field(default_factory=...)` to manage complex defaults safely and provide fast runtime/static type checks.

## Consequences
- **Pros:**
  - "Fail fast" type checking and attribute validation (especially if extended with Pydantic in the future).
  - Clear structural separation of base simulation configs vs domain-specific configs.
  - Sane default values, removing boilerplate parameter initialization code.
  - Better IDE support (autocompletion) and built-in `__repr__` and `__eq__` methods.
- **Cons:**
  - Additional classes to maintain if the configuration gets exceedingly large, though logically grouping them into domains mitigates this.
