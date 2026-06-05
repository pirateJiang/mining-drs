import sys
import os

# Ensure the root directory is on the path so we can import 'examples.mining'
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

import random
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

from examples.mining.components import ConcentratorConfig, ConcentratorModel
from drs import DRSEngine


def evaluate_throughput(config: ConcentratorConfig, N: int) -> tuple[float, float]:
    """
    Runs the simulation N times, extracting throughputs.
    Returns (mean_throughput, std_dev_throughput).
    """
    throughputs = []

    for idx in range(N):
        # By setting the replication length very high we let it hit the 6.6M extraction condition
        # and then the model automatically terminates
        sim = ConcentratorModel(config)
        engine = DRSEngine(sim)

        # Set a random seed so different replications are different
        np.random.seed(idx)
        random.seed(idx)

        engine.run(max_time=config.replication_length)

        # Calculate Throughput manually as the paper defined it
        # Throughput = Total Processed / Active Production Time (Time - Shutdown Time)
        total_time = (
            sim.controller.time_mode_a.value
            + sim.controller.time_mode_a_contingency.value
            + sim.controller.time_mode_a_surging.value
            + sim.controller.time_mode_b.value
            + sim.controller.time_mode_b_contingency.value
            + sim.controller.time_mode_b_surging.value
            + sim.controller.time_shutdown.value
        )

        active_time = total_time - sim.controller.time_shutdown.value
        if active_time > 0:
            throughput = (
                sim.plant.ore_extraction.value
                - sim.config.ore_to_be_extracted_during_warming_period
            ) / active_time
            throughputs.append(throughput)

    if not throughputs:
        return 0.0, 0.0
    return float(np.mean(throughputs)), float(np.std(throughputs))


def plot_monte_carlo_throughput(N: int = 100, total_stockpile_level: float = 60000.0):
    sigmas = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    results = []

    print(f"\n--- Running Monte Carlo Evaluation for Standard (N={N}) ---")
    for sigma in sigmas:
        config = ConcentratorConfig(
            replication_length=99999.0,
            std_dev_grade=sigma,
            target_ore_stock_level=total_stockpile_level,
        )
        mean, std = evaluate_throughput(config, N)
        results.append((sigma, mean, std))
        print(f"Sigma: {sigma}%, Mean Throughput: {mean:.2f}, Std Dev: {std:.2f}")

    # Plot results to match Figure 5 from the paper
    means = [r[1] for r in results]
    stds = [r[2] for r in results]

    plt.figure(figsize=(10, 6))
    plt.errorbar(
        sigmas,
        means,
        yerr=stds,
        fmt="-o",
        capsize=5,
        capthick=2,
        ecolor="black",
        markerfacecolor="blue",
        markeredgecolor="blue",
        color="gray",
    )

    plt.title(
        f"Expected Simulated Throughput by Geological Uncertainty (Standard, N={N})",
        fontsize=14,
    )
    plt.xlabel("Sigma geo (%)", fontsize=12)
    plt.ylabel("Mean Campaign Throughput (t/d)", fontsize=12)
    plt.ylim(5500, 6000)
    plt.grid(True, linestyle="--", alpha=0.7)

    plt.savefig(
        "Monte_Carlo_Throughput_Fig5_Standard.png", dpi=300, bbox_inches="tight"
    )
    plt.close()
    print("Saved 'Monte_Carlo_Throughput_Fig5_Standard.png'.\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--total_stockpile_level", type=float, default=60000.0)
    parser.add_argument("--std_dev_grade", type=float, default=5.0)
    parser.add_argument("--N", type=int, default=100)
    args = parser.parse_args()

    # You can also run it a single time and print out the statistics to evaluate how it spends time
    np.random.seed(42)
    random.seed(11)
    config = ConcentratorConfig(
        replication_length=99999.0,
        target_ore_stock_level=args.total_stockpile_level,
        std_dev_grade=args.std_dev_grade,
    )
    sim = ConcentratorModel(config, enable_telemetry=True)
    engine = DRSEngine(sim)
    engine.run(max_time=config.replication_length)
    sim.print_statistics()

    df = sim.telemetry.to_dataframe()

    # --- Mode Transition Log ---
    print("\n--- Mode Transition Log ---")
    df["current_mode_name"] = df["current_mode"].apply(
        lambda x: x.name if hasattr(x, "name") else str(x)
    )
    print(df["current_mode_name"].unique()[:5])
    df["prev_mode_name"] = df["current_mode_name"].shift(1)
    transitions = df[
        (df["current_mode_name"] != df["prev_mode_name"]) & df["prev_mode_name"].notna()
    ]

    for idx, row in transitions.iterrows():
        print(
            f"Time: {row['time']:.2f} | Transition: {row['prev_mode_name']} -> {row['current_mode_name']}"
        )
        print(
            f"  ↳ Ore1 Stock: {row['Ore1Stock_Level']:.1f} | Ore2 Stock: {row['Ore2Stock_Level']:.1f} (Critical: {config.critical_ore2_level}) | Total Stock: {row['OreStock_Level']:.1f} (Target: {config.target_ore_stock_level})"
        )
        print(
            f"  ↳ Campaign/Shutdown Timer: {row['TimeExecutedInCurrentCampaignOrShutdown_Timer']:.2f} | Contingency Timer: {row['TimeExecutedInCurrentContingencySegment_Timer']:.2f}"
        )
    print("---------------------------\n")

    # --- Cumulative Deficit by Mode Log ---
    import pandas as pd

    dt = df["time"].diff().fillna(0)
    actual_extraction_step = df["OreExtraction_Level"].diff().fillna(0)
    ideal_extraction_step = dt * 6000.0
    step_deficit = (ideal_extraction_step - actual_extraction_step).clip(lower=0)

    deficit_df = pd.DataFrame(
        {"mode": df["current_mode_name"], "deficit": step_deficit}
    )

    total_deficit_by_mode = (
        deficit_df.groupby("mode")["deficit"].sum().sort_values(ascending=False)
    )

    print("\n--- Cumulative Lost Production (Deficit) by Mode ---")
    total_lost = total_deficit_by_mode.sum()
    for mode, lost in total_deficit_by_mode.items():
        mode_name = str(mode).split(".")[-1]
        pct = (lost / total_lost * 100) if total_lost > 0 else 0
        print(f"{mode_name}: {lost:.1f} tons ({pct:.1f}%)")
    print(f"TOTAL: {total_lost:.1f} tons")
    print("----------------------------------------------------\n")

    # Create Modes Series
    df["Mode A"] = df["current_mode_name"].apply(
        lambda m: (
            3
            if m
            in (
                "MODE_A",
                "MODE_A_CONTINGENCY",
                "MODE_A_MINE_SURGING",
            )
            else 0
        )
    )
    df["Mode B"] = df["current_mode_name"].apply(
        lambda m: (
            2
            if m
            in (
                "MODE_B",
                "MODE_B_CONTINGENCY",
                "MODE_B_MINE_SURGING",
            )
            else 0
        )
    )
    df["Shutdown"] = df["current_mode_name"].apply(
        lambda m: 1 if m == "SHUTDOWN" else 0
    )

    # Create Ore Level Series (scaled by 1000)
    df["Total Ore Stockpile Level"] = df["OreStock_Level"] / 1000.0
    df["Ore 1 Stockpile Level"] = df["Ore1Stock_Level"] / 1000.0
    df["Ore 2 Stockpile Level"] = df["Ore2Stock_Level"] / 1000.0

    from drs.plot import (
        plot_time_series,
        plot_ore_with_modes,
        plot_dual_axis_step,
        plot_safety_margin,
        plot_state_space,
        plot_mode_distribution,
        plot_cumulative_throughput,
        plot_mode_dwell_times,
        plot_normalized_deviation_violin,
        plot_attributed_deficit,
        plot_deficit_disparity,
        plot_deficit_breakdown_bar,
        plot_structural_vs_operational_deficit,
        plot_normalized_cumulative_deficit,
        plot_structural_vs_operational_by_mode,
        build_dashboard,
    )

    palette = {
        "MODE_A": "#1f77b4",
        "MODE_A_CONTINGENCY": "#2ca02c",
        "MODE_A_MINE_SURGING": "#9467bd",
        "MODE_B": "#d62728",
        "MODE_B_CONTINGENCY": "#ff7f0e",
        "MODE_B_MINE_SURGING": "#8c564b",
        "SHUTDOWN": "#FFD700",
    }

    structural_modes = ["SHUTDOWN", "MODE_A"]

    configs = [
        {
            "func": plot_time_series,
            "kwargs": {
                "y_columns": ["Mode A", "Mode B", "Shutdown"],
                "title": "Modes (Step)",
                "is_step": True,
            },
        },
        {
            "func": plot_ore_with_modes,
            "kwargs": {
                "time_col": "time",
                "ore_cols": ["OreStock_Level", "Ore1Stock_Level", "Ore2Stock_Level"],
                "mode_col": "current_mode_name",
                "campaign_split_mode": "SHUTDOWN",
                "title": "Ore Stockpiles & Campaigns",
                "palette": palette,
                "hlines": [
                    {
                        "y": 60000,
                        "color": "black",
                        "linestyle": "--",
                        "linewidth": 1.5,
                        "alpha": 0.7,
                        "label": "Target Total (60k)",
                    },
                    {
                        "y": 20400,
                        "color": "red",
                        "linestyle": ":",
                        "linewidth": 2,
                        "alpha": 0.8,
                        "label": "Critical Ore 2 (20.4k)",
                    },
                ],
            },
        },
        {
            "func": plot_dual_axis_step,
            "kwargs": {
                "y1_col": "MassOfCurrentParcel_State",
                "y2_col": "CurrentParcelRoutingFraction_State",
                "y1_label": "Parcel Mass (tons)",
                "y2_label": "Grade (% Ore 2)",
                "title": "Current Parcel Properties",
            },
        },
        {
            "func": plot_safety_margin,
            "kwargs": {
                "level_col": "Ore1Stock_Level",
                "constraint_value": 0.0,
                "constraint_type": "lower",
                "title": "Safety Margin: Ore 1 Distance to Floor",
                "danger_threshold": 1000.0,
            },
        },
        {
            "func": plot_safety_margin,
            "kwargs": {
                "level_col": "Ore2Stock_Level",
                "constraint_value": 0.0,
                "constraint_type": "lower",
                "title": "Safety Margin: Ore 2 Distance to Floor",
                "danger_threshold": 1000.0,
            },
        },
        {
            "func": plot_mode_distribution,
            "kwargs": {
                "mode_col": "current_mode_name",
                "time_col": "time",
                "title": "Mode Distribution (% of Time Spent)",
                "palette": palette,
            },
        },
        {
            "func": plot_mode_dwell_times,
            "kwargs": {
                "time_col": "time",
                "mode_col": "current_mode_name",
                "title": "Mode Stability (Dwell Times)",
            },
        },
        {
            "func": plot_normalized_deviation_violin,
            "kwargs": {
                "title": "Stockpile Deviation Variance (Violin)",
                "target_total": 60000.0,
                "target_ore1": 42000.0,
                "target_ore2": 18000.0,
            },
        },
        {
            "func": plot_attributed_deficit,
            "kwargs": {
                "time_col": "time",
                "mode_col": "current_mode_name",
                "extraction_col": "OreExtraction_Level",
                "ideal_rate_per_day": 6000.0,
                "title": "Cumulative Production Deficit by Mode",
                "palette": palette,
            },
        },
        {
            "func": plot_deficit_disparity,
            "kwargs": {
                "mode_col": "current_mode_name",
                "title": "Mode Efficiency (Time Spent vs. Deficit Caused)",
                "ideal_rate": 6000.0,
            },
        },
        {
            "func": plot_deficit_breakdown_bar,
            "kwargs": {
                "mode_col": "current_mode_name",
                "ideal_rate_per_day": 6000.0,
                "palette": palette,
            },
        },
        {
            "func": plot_structural_vs_operational_deficit,
            "kwargs": {
                "mode_col": "current_mode_name",
                "ideal_rate": 6000.0,
                "structural_modes": structural_modes,
            },
        },
        {
            "func": plot_normalized_cumulative_deficit,
            "kwargs": {
                "mode_col": "current_mode_name",
                "ideal_rate_per_day": 6000.0,
                "palette": palette,
            },
        },
        {
            "func": plot_structural_vs_operational_by_mode,
            "kwargs": {
                "mode_col": "current_mode_name",
                "ideal_rate": 6000.0,
                "structural_modes": structural_modes,
            },
        },
    ]

    fig_comp = build_dashboard(
        df, configs, title="Comprehensive Mine Diagnostics", figsize=(18, 69)
    )
    fig_comp.savefig("Comprehensive_Diagnostics_Plot.png")

    # Recreate Figure 5 from paper
    plot_monte_carlo_throughput(
        N=args.N, total_stockpile_level=args.total_stockpile_level
    )
