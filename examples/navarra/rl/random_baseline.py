"""
Random Baseline Comparison
Mine Type: Fixed Mine
MDP Type: Event-based Semi-MDP
Action Space: Discrete

This script runs the handcoded policy (the StateMachine logic) and compares its performance
against a random baseline policy using the RL environment wrapper.
"""

import sys
import os
import random
import numpy as np

# Add standard example directory to path to import mine models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../standard")))

from env import MineEnv
from mining_drs.engine import DRSEngine
from example_mine import ExampleMineModel
from mine_config import MiningDRSConfig


def run_handcoded_policy(config):
    print("=" * 50)
    print("Running Handcoded Policy...")
    print("=" * 50)
    sim = ExampleMineModel(config)
    engine = DRSEngine(sim)
    engine.run(max_time=config.replication_length)
    sim.print_statistics()
    return sim


def run_random_policy(config):
    print("\n" + "=" * 50)
    print("Running Random Policy Baseline...")
    print("=" * 50)
    # Using the RL environment interface
    env = MineEnv(config=config)

    obs, info = (
        env.reset()
    )  # seed=42 if doing seeded training (but that doesnt make much sense)
    total_reward = 0.0
    steps = 0

    while True:
        import numpy as np
        # Sample randomly from valid actions only, because the env now fails loudly on illegal actions
        masks = env.action_masks()
        valid_actions = np.where(masks)[0]
        action = int(np.random.choice(valid_actions))

        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1

        if terminated or truncated:
            break

    print(f"\nRandom Baseline finished after {steps} steps.")
    print(f"Total Accumulated Reward: {total_reward:.2f}")
    env.sim.print_statistics()
    return env.sim


if __name__ == "__main__":
    # Ensure reproducibility for comparison
    # seed = 42
    # random.seed(seed)
    # np.random.seed(seed)

    # Use a slightly shorter replication length to ensure the random policy finishes in a reasonable time if it's very inefficient
    # Though DRS is usually fast enough for 99999.0
    config = MiningDRSConfig(
        replication_length=30000.0,
    )

    handcoded_sim = run_handcoded_policy(config)

    # Reset seeds so the random environment starts from the same initial conditions
    # random.seed(seed)
    # np.random.seed(seed)

    random_sim = run_random_policy(config)

    print("\n" + "=" * 50)
    print("Comparison Summary")
    print("=" * 50)

    def get_throughput(sim):
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
            return (
                sim.plant.ore_extraction.value
                - sim.config.ore_to_be_extracted_during_warming_period
            ) / active_time
        return 0.0

    hc_throughput = get_throughput(handcoded_sim)
    rand_throughput = get_throughput(random_sim)

    print(f"Handcoded Policy Throughput: {hc_throughput:.4f} tons/day")
    print(f"Random Baseline Throughput:  {rand_throughput:.4f} tons/day")

    if hc_throughput > rand_throughput:
        print(
            f"-> Handcoded policy outperformed Random baseline by {hc_throughput - rand_throughput:.4f} tons/day."
        )
    else:
        print(
            f"-> Random baseline outperformed Handcoded policy by {rand_throughput - hc_throughput:.4f} tons/day."
        )

    print("\nGenerating side-by-side plots...")
    import matplotlib.pyplot as plt
    from example_mine import MineMode

    df_hc = handcoded_sim.telemetry.to_dataframe()
    df_rand = random_sim.telemetry.to_dataframe()

    def prepare_df(df):
        df["Mode A"] = df["current_mode"].apply(
            lambda m: (
                3
                if m
                in (
                    MineMode.MODE_A,
                    MineMode.MODE_A_CONTINGENCY,
                    MineMode.MODE_A_MINE_SURGING,
                )
                else 0
            )
        )
        df["Mode B"] = df["current_mode"].apply(
            lambda m: (
                2
                if m
                in (
                    MineMode.MODE_B,
                    MineMode.MODE_B_CONTINGENCY,
                    MineMode.MODE_B_MINE_SURGING,
                )
                else 0
            )
        )
        df["Shutdown"] = df["current_mode"].apply(
            lambda m: 1 if m == MineMode.SHUTDOWN else 0
        )
        df["Total Ore Stockpile Level"] = df["OreStock_Level"] / 1000.0
        df["Ore 1 Stockpile Level"] = df["Ore1Stock_Level"] / 1000.0
        df["Ore 2 Stockpile Level"] = df["Ore2Stock_Level"] / 1000.0
        return df

    df_hc = prepare_df(df_hc)
    df_rand = prepare_df(df_rand)

    # Plot Ore levels side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

    # Handcoded
    ax1.plot(df_hc.index, df_hc["Total Ore Stockpile Level"], label="Total")
    ax1.plot(df_hc.index, df_hc["Ore 1 Stockpile Level"], label="Ore 1")
    ax1.plot(df_hc.index, df_hc["Ore 2 Stockpile Level"], label="Ore 2")
    ax1.set_title("Handcoded Policy: Ore Levels")
    ax1.set_ylabel("Ore Level (Thousands of Tons)")
    ax1.set_ylim(0, 80)
    ax1.legend()

    # Random
    ax2.plot(df_rand.index, df_rand["Total Ore Stockpile Level"], label="Total")
    ax2.plot(df_rand.index, df_rand["Ore 1 Stockpile Level"], label="Ore 1")
    ax2.plot(df_rand.index, df_rand["Ore 2 Stockpile Level"], label="Ore 2")
    ax2.set_title("Random Baseline: Ore Levels")
    ax2.set_ylim(0, 80)
    ax2.legend()

    fig.tight_layout()
    fig.savefig(os.path.join(os.path.dirname(__file__), "Ore_Levels_Comparison.png"))

    # Plot Modes side by side
    fig2, (ax3, ax4) = plt.subplots(1, 2, figsize=(15, 5))

    # Handcoded
    ax3.step(df_hc.index, df_hc["Mode A"], label="Mode A", where="post")
    ax3.step(df_hc.index, df_hc["Mode B"], label="Mode B", where="post")
    ax3.step(df_hc.index, df_hc["Shutdown"], label="Shutdown", where="post")
    ax3.set_title("Handcoded Policy: Modes")
    ax3.set_ylabel("Mode State")
    ax3.set_ylim(0, 4)
    ax3.set_yticks([0, 1, 2, 3, 4])
    ax3.legend()

    # Random
    ax4.step(df_rand.index, df_rand["Mode A"], label="Mode A", where="post")
    ax4.step(df_rand.index, df_rand["Mode B"], label="Mode B", where="post")
    ax4.step(df_rand.index, df_rand["Shutdown"], label="Shutdown", where="post")
    ax4.set_title("Random Baseline: Modes")
    ax4.set_ylim(0, 4)
    ax4.set_yticks([0, 1, 2, 3, 4])
    ax4.legend()

    fig2.tight_layout()
    fig2.savefig(os.path.join(os.path.dirname(__file__), "Modes_Comparison.png"))

    print(f"Plots saved to {os.path.dirname(__file__)}")
