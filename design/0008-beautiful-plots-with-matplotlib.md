# ADR 0008: Beautiful Plots with Matplotlib

## Status
Accepted

## Context
Standard Arena setups output data that often requires copying into Excel to create basic static plots. This manual step disrupts the analysis workflow and limits the depth of exploration. We need a mechanism to instantly generate presentation-ready visualizations directly from the simulation data.

## Decision
We utilize `matplotlib` for all core visual telemetry outputs. 
- Because our `Telemetry` class seamlessly exports a `pandas.DataFrame` (ADR 0007), we can pipe that data directly into Matplotlib.
- A central `plot.py` module will house wrapper functions (e.g., `plot_time_series`) to standardize the aesthetic (colors, layouts) across all plots without rewriting Matplotlib boilerplate.
- The plots will be high-quality static charts suitable for saving, embedding, or publication.

## Consequences
- **Pros:**
  - Zero-friction transition from simulation completion to beautiful analysis.
  - Highly customizable, industry-standard library for scientific plotting.
  - Publication-ready quality out of the box.
- **Cons:**
  - Adds a dependency on `matplotlib` and `pandas`.
  - Static by default, though interactive backends exist.
