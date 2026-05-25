# ADR 0005: Formula Parser for Arena Expressions

## Status
Accepted

## Context
In the original Arena setup, logical expressions (such as `"""MX(NORM(parameter1, parameter2),0)"""` or `UNIF(0,1)`) are imported from Excel and evaluated as strings at runtime. This practice is slow due to the overhead of string evaluation on every simulation tick and is prone to silent errors that manifest late in the execution.

## Decision
We implement a `FormulaParser` class to translate Arena-specific expressions into native Python functions (closures/lambdas) during initialization.
- **Mapping**: Arena functions (e.g., `UNIF`, `NORM`, `MX`) are mapped to Python's `numpy.random` and built-in math functions.
- **Initialization Compilation**: Expressions are parsed once when the simulation starts. The parser returns a callable Python function that can be executed natively in the simulation loop.
- **AST/Safe Parsing**: While a full AST parser can be used, we map specific patterns to Python logic safely without using raw `eval()` in the tick loop.

## Consequences
- **Pros:**
  - **Fail Fast**: Syntax errors (e.g., typing `NROM` instead of `NORM`) raise exceptions at initialization, preventing late-stage crashes.
  - **Performance**: Natively compiled Python closures are lightning-fast compared to evaluating strings repeatedly.
  - Eliminates the need for dynamic string execution (like `eval()`), increasing security and stability.
- **Cons:**
  - Requires maintaining a regex/parsing logic or AST translator for any new Arena syntax introduced to the configuration.
