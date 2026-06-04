# Modular Simulation Testing Suite

Bugs in simulation engines and control systems are rarely loud crashes; they are often silent errors—a miscalculated capacity, a broken state transition, or a faulty telemetry variable.

This testing suite is designed to rigorously verify the underlying logic and mathematics of the `mining-drs` codebase, adopting the modular, tiered testing philosophy used in reinforcement learning frameworks.

## 📁 Organization Philosophy

This directory uses a **hybrid organization strategy**:
1. **Unit Tests** strictly mirror the source code directory structure (or key modules).
2. **Integration, Smoke, and Regression Tests** are organized by system interaction.

```text
tests/
├── conftest.py                             # Global fixtures (seeded random numbers)
│
├── unit/                                   # Tier 1: Isolated logic checks
│   ├── test_engine.py                      #   ↳ e.g., Simulation steps and queues
│   ├── test_variables.py                   #   ↳ e.g., Telemetry variable bounds
│   └── ...                                 #
│
├── integration/                            # Tier 2: Component interaction
│   └── test_navarra_arena_semantics.py     #   ↳ e.g., Complex transition logic
│
├── smoke/                                  # Tier 3: Execution targets
│   └── test_full_simulation.py             #   ↳ Fast 10-step full simulation loops (planned)
│
├── regression/                             # Tier 4: Feature verification
│   └── test_issue_fixes.py                 #   ↳ Ensures old bugs don't return (planned)
│
└── performance/                            # Tier 5: Throughput and Efficiency
    └── test_simulation_speed.py            #   ↳ Steps per second benchmarks (planned)
```

🚥 The 5-Tier Testing Pipeline
To maintain high developer velocity while ensuring mathematical rigor, tests are divided into five tiers based on execution time and determinism:

Tier 1: Unit (Core Logic & Variables)
Scope: Isolated functions (engine math, configuration bounds, discrete states).
Execution: Runs in milliseconds.
CI Target: Runs on every single push.

Tier 2: Integration (Component Wiring)
Scope: Ensures modules wire together correctly (e.g., controllers managing plants).
Execution: Runs in seconds.
CI Target: Runs on every Pull Request.

Tier 3: Smoke Tests (Execution Loops)
Scope: Short simulation loops. Asserts that the loop runs, logs, and checkpoints without crashing, not that the policy is optimal.
Execution: Runs in seconds to minutes.
CI Target: Runs Nightly.

Tier 4: Regression (Feature Verification)
Scope: Validating that specific modes and bounds continue to respect previously fixed issues.
Execution: Runs in minutes.
CI Target: Runs on Releases.

Tier 5: Performance (Benchmarks)
Scope: Measure throughput (steps per second) to prevent silent regressions in simulation speed.
Execution: Runs in minutes.
CI Target: Runs Nightly.

## 🤝 Contract Testing: Protecting Architectural Assumptions

Contract tests verify the strict formatting agreements between modules (e.g., config limits, variable clamping) without validating the complex mathematical simulation. These live inside `tests/unit/` and execute in Tier 1.

### The Core Simulation Contracts

When adding or modifying components, ensure the following contracts are explicitly tested:

**1. The Bounds Contract**
* **The Rule:** Variables with defined lower and upper bounds must clamp or trigger transitions accurately.
* **The Test:** Set a `ContinuousVariable` to exactly its bound, below its bound, and above its bound. Assert the value is handled correctly.

**2. The State Machine Contract**
* **The Rule:** The controller must transition modes according to precisely defined conditions.
* **The Test:** Mock the plant state and assert that the `check_transitions` function mutates the `current_mode` as expected.

⚖️ The 4 Rules of Test Driven Development
When adding tests to this repository, strictly adhere to the following rules:

Strict Determinism: Simulation tests must be 100% reproducible. Rely on fixtures in `conftest.py` that strictly seed `numpy` and `random` before every test. Flaky tests are failing tests.

Explicit Variable Types: Ensure you are testing continuous vs. discrete variables appropriately.

The "Analytical Oracle" Rule: For complex rate logic, calculate the expected output by hand for a small tick (e.g., delta=1). Hardcode those exact float values into the test.

Isolate Logic: Unit tests should mock the opposing side. If testing the controller, mock the plant's current state. If testing the plant, mock the controller's rates.

🚀 Getting Started
Run the fast unit tests locally before pushing:

```bash
pytest tests/unit/
```

Run tests with print statements for debugging:

```bash
pytest tests/unit/ -s
```

Run performance tests and generate benchmark JSON:

```bash
pytest tests/performance/ --benchmark-json=new_benchmarks.json
```
