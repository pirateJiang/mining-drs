import sys
import os
import random
import numpy as np
import matplotlib.pyplot as plt

# Ensure the root directory is on the path so we can import 'examples.mining'
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

from examples.mining.components.config import CyanidationConfig
from examples.mining.components.models import CyanidationModel
from drs import DRSEngine


# TODO: results and plot values look very different.
def evaluate_scenario(
    config: CyanidationConfig, N: int
) -> tuple[float, float, float, float]:
    """
    Runs the simulation N times.
    Returns (mean_throughput, std_dev_throughput, mean_cyanide, std_dev_cyanide).
    """
    throughputs = []
    cyanide_consumptions = []

    for idx in range(N):
        sim = CyanidationModel(config)
        engine = DRSEngine(sim)

        np.random.seed(idx)
        random.seed(idx)

        engine.run(max_time=config.replication_length)

        # Real throughput calculation excluding shutdown
        active_time = (
            sim.controller.time_mode_a.value
            + sim.controller.time_mode_a_contingency.value
            + sim.controller.time_mode_a_surging.value
            + sim.controller.time_mode_b.value
            + sim.controller.time_mode_b_contingency.value
            + sim.controller.time_mode_b_surging.value
        )
        if hasattr(sim.controller, "time_mode_c"):
            active_time += (
                sim.controller.time_mode_c.value
                + sim.controller.time_mode_c_contingency.value
                + sim.controller.time_mode_c_surging.value
                + sim.controller.time_mode_d.value
                + sim.controller.time_mode_d_contingency.value
                + sim.controller.time_mode_d_surging.value
            )

        if hasattr(sim.plant, "total_ore_milled"):
            total_ore_processed = sim.plant.true_total_ore_milled.value
        else:
            total_ore_processed = sim.mine.true_ore_extraction.value - config.ore_to_be_extracted_during_warming_period

        total_cyanide_used = sim.plant.true_total_cyanide_consumed.value

        empirical_avg_cyanide = 0.0
        if total_ore_processed > 0:
            empirical_avg_cyanide = total_cyanide_used / total_ore_processed

        if active_time > 0 and total_ore_processed > 0:
            throughput = total_ore_processed / active_time
            throughputs.append(throughput)
            cyanide_consumptions.append(empirical_avg_cyanide)

    if not throughputs:
        return 0.0, 0.0, 0.0, 0.0

    return (
        float(np.mean(throughputs)),
        float(np.std(throughputs)),
        float(np.mean(cyanide_consumptions)),
        float(np.std(cyanide_consumptions)),
    )


def run_grid_evaluation(
    stage: int,
    N: int,
    X_values: list[float],
    pct_values: list[float],
    output_prefix: str,
):
    print(f"\n--- Running Monte Carlo Evaluation for Stage {stage} (N={N}) ---")

    # Dictionaries to hold results keyed by X, lists parallel to pct_values
    results_tp = {X: [] for X in X_values}
    results_cn = {X: [] for X in X_values}

    stage_2_start_period = 9999 if stage == 1 else 0

    for X in X_values:
        print(f"\nEvaluating Target Total Stockpile Level (X) = {X}")
        for pct in pct_values:
            Y = X * pct / 100.0
            print(
                f"  Running Policy: Target={X}, Critical={Y} ({pct}%)...",
                end=" ",
                flush=True,
            )

            # Stage 1 (Configurations A & B)
            # A: 2000 total (20% Ore 1 / 80% Ore 2), Cont: 1300 (100% Ore 1)
            # B: 1700 total (45% Ore 1 / 55% Ore 2), Cont: 850 (100% Ore 2)
            # Stage 2 (Configurations C & D)
            # C: 2750 total (40% Ore 1 / 60% Ore 2), Cont: 1790 (100% Ore 1)
            # D: 2340 total (55% Ore 1 / 45% Ore 2), Cont: 1170 (100% Ore 2)

            config = CyanidationConfig(
                replication_length=1500.0,
                total_ore_to_extract=100_000_000.0,  # Prevent early termination deadlock
                target_ore_stock_level=X,
                critical_ore2_level=Y,
                stage_2_start_period=stage_2_start_period,
                # Config A
                mode_a_ore1_milling_rate=2000.0 * 0.20,
                mode_a_ore2_milling_rate=2000.0 * 0.80,
                mode_a_contingency_ore1_milling_rate=1300.0 * 1.0,
                # Config B
                mode_b_ore1_milling_rate=1700.0 * 0.45,
                mode_b_ore2_milling_rate=1700.0 * 0.55,
                mode_b_contingency_ore2_milling_rate=850.0 * 1.0,
                # Config C
                mode_c_ore1_milling_rate=2750.0 * 0.40,
                mode_c_ore2_milling_rate=2750.0 * 0.60,
                mode_c_contingency_ore1_milling_rate=1790.0 * 1.0,
                # Config D
                mode_d_ore1_milling_rate=2340.0 * 0.55,
                mode_d_ore2_milling_rate=2340.0 * 0.45,
                mode_d_contingency_ore2_milling_rate=1170.0 * 1.0,
            )

            mean_tp, std_tp, mean_cn, std_cn = evaluate_scenario(config, N)
            print(f"Mean Throughput: {mean_tp:.2f}, Mean Cyanide: {mean_cn:.2f} kg/t")

            results_tp[X].append(mean_tp)
            results_cn[X].append(mean_cn)

    markers = ["o", "s", "^"]

    # 1. Plot Figure A (Throughput)
    plt.figure(figsize=(10, 6))
    for i, X in enumerate(X_values):
        plt.plot(
            pct_values, results_tp[X], marker=markers[i], linestyle="--", label=f"{X} t"
        )

    plt.title(f"Stage {stage} Average Daily Throughput")
    plt.xlabel("Ore 2 critical level respect the Target (%)")
    plt.ylabel("Throughput [t/day]")
    plt.xticks(pct_values, [f"{int(pct)}%" for pct in pct_values])
    plt.legend(title="Total Ore Stockpile Level")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.savefig(f"{output_prefix}_Throughput.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 2. Plot Figure B (Cyanide)
    plt.figure(figsize=(10, 6))
    for i, X in enumerate(X_values):
        plt.plot(
            pct_values, results_cn[X], marker=markers[i], linestyle="--", label=f"{X} t"
        )

    plt.title(f"Stage {stage} Average Daily Cyanide Consumption")
    plt.xlabel("Ore 2 critical level respect the Target (%)")
    plt.ylabel("Cyanide Consumption [Kg/Ton]")
    plt.xticks(pct_values, [f"{int(pct)}%" for pct in pct_values])
    plt.legend(title="Total Ore Stockpile Level")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.savefig(f"{output_prefix}_Cyanide.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 3. Plot Pareto Frontier (Throughput vs Cyanide)
    plt.figure(figsize=(10, 6))
    for i, X in enumerate(X_values):
        plt.scatter(results_tp[X], results_cn[X], marker=markers[i], label=f"{X} t")
        # Annotate points with their %
        for j, pct in enumerate(pct_values):
            plt.annotate(
                f"{pct}%",
                (results_tp[X][j], results_cn[X][j]),
                textcoords="offset points",
                xytext=(0, 5),
                ha="center",
                fontsize=8,
            )

    plt.title(f"Stage {stage} Pareto Frontier (Throughput vs Cyanide)")
    plt.xlabel("Mean Throughput [t/day]")
    plt.ylabel("Mean Cyanide Consumption [Kg/Ton]")
    plt.legend(title="Total Ore Stockpile Level")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.savefig(f"{output_prefix}_Pareto.png", dpi=300, bbox_inches="tight")
    plt.close()

    print(
        f"\nSaved plots for Stage {stage} to {output_prefix}_Throughput.png, {output_prefix}_Cyanide.png, and {output_prefix}_Pareto.png"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--N", type=int, default=50, help="Number of Monte Carlo replications"
    )
    args = parser.parse_args()

    pct_values = [0, 10, 25, 50, 75, 90, 100]

    # Stage 1: X = 4000, 5000, 6000
    run_grid_evaluation(
        stage=1,
        N=args.N,
        X_values=[4000.0, 5000.0, 6000.0],
        pct_values=pct_values,
        output_prefix="Monte_Carlo_Fig20_Stage1",
    )

    # Stage 2: X = 6000, 8000, 10000
    run_grid_evaluation(
        stage=2,
        N=args.N,
        X_values=[6000.0, 8000.0, 10000.0],
        pct_values=pct_values,
        output_prefix="Monte_Carlo_Fig21_Stage2",
    )

    print("\nAll evaluations complete!")
