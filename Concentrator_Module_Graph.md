# DRS Module Graph — ConcentratorModel

> Generated automatically by `drs.vis.module_graph.save_module_graph_report`

## Module Hierarchy

| Name | Path | Type | Variables |
|------|------|------|-----------|
| `ConcentratorModel` | `(root)` | model | `global_time` |
| `generator` | `generator` | generator | `—` |
| `mine` | `mine` | mine | `true_current_parcel_mass, true_ore_extraction, true_ore_extracted_from_current_parcel, true_current_parcel_grade` |
| `fleet` | `fleet` | fleet | `fraction_to_ore2` |
| `true_ore1_stock` | `true_ore1_stock` | stockpile | `mass, actual_outflow, grade` |
| `true_ore2_stock` | `true_ore2_stock` | stockpile | `mass, actual_outflow, grade` |
| `plant` | `plant` | plant | `true_ore_stock, true_total_ore_milled` |
| `controller` | `controller` | controller | `current_mode, time_executed_campaign_shutdown, time_executed_contingency, time_mode_a, time_mode_a_contingency, +5 more` |

## Flowchart

```mermaid
flowchart TD
    classDef controller fill:#FF6B6B,stroke:#333,color:#111
    classDef stockpile fill:#ED7D31,stroke:#333,color:#111
    classDef plant fill:#70AD47,stroke:#333,color:#111
    classDef fleet fill:#5B9BD5,stroke:#333,color:#111
    classDef mine fill:#D4A574,stroke:#333,color:#111
    classDef generator fill:#00BCD4,stroke:#333,color:#111
    classDef model fill:#555555,stroke:#333,color:#111
subgraph root["ConcentratorModel (model)"]
    generator(["generator (generator)"]):::generator
    mine(["mine (mine)"]):::mine
    fleet(["fleet (fleet)"]):::fleet
    true_ore1_stock(["true_ore1_stock (stockpile)"]):::stockpile
    true_ore2_stock(["true_ore2_stock (stockpile)"]):::stockpile
    plant(["plant (plant)"]):::plant
    controller(["controller (controller)"]):::controller
end
    fleet -->|fraction_to_ore2| mine
    mine -->|true_parcel_grade| fleet
    true_ore1_stock -->|TrueOre1Stock_mass| plant
    true_ore2_stock -->|TrueOre2Stock_mass| plant
    mine -->|TrueOreExtraction_Level| controller
    true_ore1_stock -->|TrueOre1Stock_mass| controller
    true_ore2_stock -->|TrueOre2Stock_mass| controller
    plant -->|TrueOreStock_Level| controller
    controller ==>|flow| mine
    mine ==>|flow| true_ore1_stock
    fleet ==>|flow| true_ore1_stock
    mine ==>|flow| true_ore2_stock
    fleet ==>|flow| true_ore2_stock
    true_ore1_stock ==>|flow| plant
    true_ore2_stock ==>|flow| plant
    generator -.->|data| mine
    fleet -.->|routing| true_ore1_stock
    fleet -.->|routing| true_ore2_stock
```

## Data Dependencies (persistent variable reads)

The following read-dependencies were recorded during the simulation. An arrow `A → B` means module B reads a variable owned by module A.

  - `mine` → `ConcentratorModel` reads `TrueOreExtraction_Level`
  - `fleet` → `ConcentratorModel` reads `fraction_to_ore2`
  - `mine` → `ConcentratorModel` reads `true_parcel_grade`
  - `fleet` → `mine` reads `fraction_to_ore2`
  - `mine` → `fleet` reads `true_parcel_grade`
  - `true_ore1_stock` → `plant` reads `TrueOre1Stock_mass`
  - `true_ore2_stock` → `plant` reads `TrueOre2Stock_mass`
  - `mine` → `controller` reads `TrueOreExtraction_Level`
  - `true_ore1_stock` → `controller` reads `TrueOre1Stock_mass`
  - `true_ore2_stock` → `controller` reads `TrueOre2Stock_mass`
  - `plant` → `controller` reads `TrueOreStock_Level`

## Data Flow (transient)

The following transient flow-edges were recorded during the simulation. An arrow `A → B` means module A returned a `drs.Flow` value that was passed as input to module B.

  - `controller` → `mine` flow
  - `mine` → `true_ore1_stock` flow
  - `fleet` → `true_ore1_stock` flow
  - `mine` → `true_ore2_stock` flow
  - `fleet` → `true_ore2_stock` flow
  - `true_ore1_stock` → `plant` flow
  - `true_ore2_stock` → `plant` flow

## Visual Graph

![Module Graph](Concentrator_Module_Graph.png)
