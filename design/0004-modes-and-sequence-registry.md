# ADR 0004: Command Pattern and Callables for Mode Sequences

## Status
Accepted

## Context
In previous legacy implementations or generic Arena models, complex behavioral logic (sequences based on mode transitions) was often mapped using obscure logic (e.g., `X * (condition < Y)` or `MN(...)`) or by loading Excel expression strings at runtime (e.g., `Eval(ConfExString)`). This leads to weak typing, poor error messages, limited debuggability, and performance hits from parsing strings into expressions at runtime.

## Decision
We utilize the Command Pattern mapping to pure Python functions. 
- **Modes**: Defined explicitly using Python `Enum` classes (e.g., `MiningMode`).
- **Sequences**: Handled by a `SequenceRegistry` that maps specific Enums to callable Python functions.
- **Evaluation**: The Python functions receive a `context` (often the engine or current state) and evaluate standard `if/else`, `min()`, or `max()` statements, avoiding any string `eval()`.

## Consequences
- **Pros:**
  - Secure and structured evaluation. No more raw string evaluations.
  - Fail fast functionality on missing logic; if a mode isn't registered in the registry, it explicitly throws an error immediately.
  - Significantly improved readability and IDE support (navigation, refactoring, type checking).
- **Cons:**
  - Configuration logic is now natively in Python code, meaning configuration requires modifying or injecting Python functions rather than purely editing an external Excel file.
