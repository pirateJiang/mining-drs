# ADR 0006: Ore Body Model and Spatial Correlation

## Status
Accepted

## Context
In legacy systems like Arena, the "Earth Model" and the "Simulation Engine" are tightly coupled. Due to Arena's queueing nature, mining geostatistics are typically simulated by treating the earth as a series of independent random number generations (e.g., pulling a `NORM` value for each parcel). This approach ignores spatial correlation—the fundamental principle that the ore grade of one parcel is highly correlated to the parcels surrounding it. 

## Decision
We decouple the "Earth Model" from the simulation loop by introducing an `OreBodyModel` class.
- Rather than drawing random distributions on the fly for every tick/parcel, the `OreBodyModel` pre-generates a spatially correlated Block Model grid during initialization.
- In advanced implementations, this grid can be generated using true geostatistical libraries (e.g., `scikit-gstat` for Kriging or `GeostatsPy` for Sequential Gaussian Simulation).
- The simulation engine then sequentially queries the `OreBodyModel` for the next physical parcel, fully separating the geological reality from the mechanical simulation constraints.

## Consequences
- **Pros:**
  - True representation of geology, enabling accurate localized uncertainty analysis.
  - Decoupling allows for swapping out different block models easily without changing the simulation logic.
  - Reduced runtime cost: array lookups during the simulation loop are much faster than calculating complex probabilistic draws on the fly.
- **Cons:**
  - Generating complex 3D spatially correlated block models requires more memory and computational time up front during initialization.
