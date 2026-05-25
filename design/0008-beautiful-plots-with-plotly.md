# ADR 0008: Beautiful Plots with Plotly

## Status
Accepted

## Context
Standard Arena setups output data that often requires copying into Excel to create basic static plots. This manual step disrupts the analysis workflow and limits the depth of exploration (e.g., no easy zooming, panning, or filtering). We need a mechanism to instantly generate interactive, presentation-ready visualizations directly from the simulation data.

## Decision
We utilize `plotly.express` for all core visual telemetry outputs. 
- Because our `Telemetry` class seamlessly exports a `pandas.DataFrame` (ADR 0007), we can pipe that data directly into Plotly in just a few lines of code.
- A central `plot.py` module will house wrapper functions (e.g., `plot_time_series`) to standardize the aesthetic (colors, layouts) across all plots without rewriting Plotly boilerplate.
- The plots will be interactive HTML charts by default, allowing engineers to drill down into specific timeline events visually.

## Consequences
- **Pros:**
  - Zero-friction transition from simulation completion to beautiful, interactive analysis.
  - Interactive charts significantly enhance debugging by allowing zooming in on threshold crossover events.
  - Publication-ready quality out of the box.
- **Cons:**
  - Adds a dependency on `plotly` and `pandas`.
  - HTML rendering might be slightly slower than generating a flat `.png`, though the interactive benefits far outweigh this.
