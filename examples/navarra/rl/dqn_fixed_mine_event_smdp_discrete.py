"""
Algorithm: DQN (Deep Q-Network)
Mine Type: Fixed Mine
MDP Type: Event-based Semi-MDP
Action Space: Discrete

Design Decisions & Changes from `rl-stuff/examples/dqn/dqn_cartpole.py`:
1.  **SMDP Discounting**: Since the simulation is an Event-based Semi-MDP where each decision has a variable duration, we use mathematically rigorous SMDP discounting by $ \gamma^{\Delta t} $. We extract `time_elapsed` from the environment `info` dict and apply it to the transition `gamma`. This may be slightly different than the MDP case which would have throughputs at each step each discounted. TODO: do we sum throughputs until the next event or do the mean? or just give the throughput at the new event?
2.  **Warmup Phase**: Added a warmup phase (`MIN_BUFFER_SIZE = 1000`) where the agent takes purely random actions to populate the replay buffer before starting updates. This is standard in DQN to prevent early overfitting to highly correlated initial trajectories.
3.  **W&B Logging**: Kept W&B logging, but added a check or set mode to "disabled" to prevent issues if the user isn't logged in, as this is an example script. (I will use mode="disabled" by default to ensure it runs without requiring user login, but leave the code intact).
4.  **Network Output**: Kept the same simple MLP architecture `(Linear(obs_dim, 512) -> ReLU -> Linear(512, 512) -> ReLU -> Linear(512, num_actions))`, as the observation space is likely a flat vector (Box).
5.  **Environment Config**: Configured `MiningDRSConfig` with a shorter `replication_length` for faster training episodes (e.g., 30000.0 instead of default 100000.0).
6.  **Evaluation**: Added an evaluation phase after training that runs the trained policy greedily for one episode and generates comparison plots against the Random Baseline and Handcoded policy, similar to `random_baseline.py`.

Bug Fixes vs *Original* `rl-stuff` Example:
1.  **Action Indexing (`int()` casting)**: In `rl-stuff`, the action passed to `env.step()` was a 0D NumPy array (`action_np`). `gym.make("CartPole-v1")` accepts this, but our custom `MineEnv` uses the action to index a list (`self.allowed_modes[action]`), which requires a strict Python `int`. I added an explicit `int(action_np.item())` cast to prevent `TypeError: only integer scalar arrays can be converted to a scalar index`.
2.  **Buffer State Size Access**: The `rl-stuff` example accessed the buffer size via `buffer_state['size'].item()`. However, `buffer_state` returned from `init_buffer` is a named tuple or dataclass where `size` is a native integer attribute, not a tensor or dict key. I changed this to `buffer_state.size` to fix `TypeError` and `AttributeError` exceptions during logging.

*(Note: The `to_tensor` `dtype` kwarg bug has since been patched upstream in `rl-stuff`)*
"""

import sys
import os
import random
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import wandb
from tensordict import TensorDict
from typing import Tuple

# Add rl-stuff to path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../rl-stuff"))
)

from functional.initialization import layer_init, set_seed
from functional.replay_buffer import (
    init_buffer,
    circular_write_strategy,
    uniform_sample,
)
from functional.losses import mse_loss
from functional.td import compute_q_td_target
from functional.action_selection import (
    argmax_selector,
    gather_q_values,
    with_epsilon_greedy,
    apply_action_mask,
)
from functional.schedules import get_linear_schedule
from functional.optimizer import apply_gradients
from functional.network import hard_update_target_network
from functional.utils import (
    to_tensor,
    to_numpy_action,
)

# Add standard example directory to path to import mine models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../standard")))

from env import MineEnv
from mine_config import MiningDRSConfig

# Constants
BATCH_SIZE = 128
GAMMA = 0.99
EPS_START = 1.0
EPS_END = 0.05
EPS_DECAY_FRAMES = 50000
LEARNING_RATE = 1e-3
MAX_STEPS = 100_000  # Enough for a few episodes
UPDATE_FREQ = 4
BUFFER_CAPACITY = 50000
MIN_BUFFER_SIZE = 1000  # Warmup phase!
TARGET_NET_UPDATE_FREQ = 100
SEED = 42


class DQN(nn.Module):
    def __init__(self, input_shape: Tuple, num_actions: int):
        super().__init__()
        # Ensure input_shape[0] works for our observation space
        in_features = input_shape[0] if isinstance(input_shape, tuple) else input_shape
        self.l1 = layer_init(nn.Linear(in_features, 512))
        self.l2 = layer_init(nn.Linear(512, 512))
        self.l3 = layer_init(nn.Linear(512, num_actions), std=1.0)

    def forward(self, x):
        x = F.relu(self.l1(x))
        x = F.relu(self.l2(x))
        x = self.l3(x)
        return x


def run_dqn_training(env, config, seed=SEED):
    set_seed(seed)

    obs_shape = env.observation_space.shape
    num_actions = env.action_space.n
    device = torch.device("cpu")

    model = DQN(obs_shape, num_actions).to(device)
    target_model = DQN(obs_shape, num_actions).to(device)
    target_model.load_state_dict(model.state_dict())

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    buffer_state = init_buffer(
        capacity=BUFFER_CAPACITY,
        shapes={
            "obs": obs_shape,
            "action": (1,),
            "reward": (),
            "terminated": (),
            "truncated": (),
            "next_obs": obs_shape,
            "gamma": (),
            "mask": (num_actions,),
            "next_mask": (num_actions,),
        },
        device=device,
    )

    obs, info = env.reset(seed=seed)
    rng_key = torch.Generator(device=device)
    rng_key.manual_seed(seed)

    action_selector = with_epsilon_greedy(argmax_selector)

    # Initialize W&B (disabled to prevent auth issues for users running the example)
    wandb.init(
        project="dqn-mine-env",
        mode="disabled",
        config={
            "batch_size": BATCH_SIZE,
            "gamma": GAMMA,
            "learning_rate": LEARNING_RATE,
            "buffer_capacity": BUFFER_CAPACITY,
        },
    )

    print("=" * 50)
    print("Starting DQN Training...")
    print("=" * 50)

    episode_returns = []
    losses = []
    epsilons = []
    current_return = 0.0

    for step in range(MAX_STEPS):
        current_epsilon = get_linear_schedule(
            step, EPS_START, EPS_END, EPS_DECAY_FRAMES
        )
        epsilons.append(current_epsilon)

        with torch.inference_mode():
            # Get Action Mask (Boolean NumPy Array -> Tensor)
            mask_np = env.action_masks()
            mask_tensor = to_tensor(mask_np[None, ...], dtype=torch.bool, device=device)

            obs_tensor = to_tensor(obs[None, ...], device=device)
            predictions = model(obs_tensor)

            # Mask out invalid actions so the greedy selector doesn't choose them
            predictions = apply_action_mask(predictions, mask_tensor)

            action, info_sel = action_selector(
                predictions=predictions,
                epsilon=current_epsilon,
                num_actions=num_actions,
                generator=rng_key,
                mask=mask_tensor,
            )
            rng_key = info_sel["generator"]
            action_np = to_numpy_action(action)
            action_int = int(action_np.item())

        next_obs, reward, terminated, truncated, info = env.step(action_int)

        # Precise SMDP discounting based on elapsed time (dt)
        dt = info.get("time_elapsed", 1.0)
        smdp_gamma = GAMMA**dt

        next_mask_np = env.action_masks()

        transition = {
            "obs": to_tensor(obs),
            "action": action.squeeze(0).detach().to(torch.long),
            "reward": to_tensor(reward, dtype=torch.float32),
            "terminated": to_tensor(terminated, dtype=torch.bool),
            "truncated": to_tensor(truncated, dtype=torch.bool),
            "next_obs": to_tensor(next_obs),
            "gamma": to_tensor(smdp_gamma, dtype=torch.float32),
            "mask": mask_tensor.squeeze(0),
            "next_mask": to_tensor(next_mask_np, dtype=torch.bool, device=device),
        }
        buffer_state, _ = circular_write_strategy(
            buffer_state, TensorDict(transition, batch_size=[]).unsqueeze(0)
        )

        current_return += reward
        obs = next_obs

        if terminated or truncated:
            episode_returns.append(current_return)
            current_return = 0.0
            obs, info = env.reset()

        if step > MIN_BUFFER_SIZE and step % UPDATE_FREQ == 0:
            batch = uniform_sample(buffer_state, rng_key, BATCH_SIZE)

            q_values = model(batch["obs"])
            with torch.no_grad():
                next_q_values = target_model(batch["next_obs"])
                # FIX: Prevent bootstrapping from invalid actions
                next_q_values = apply_action_mask(next_q_values, batch["next_mask"])
                next_actions, _ = argmax_selector(next_q_values)
                td_target = compute_q_td_target(
                    next_q_values,
                    next_actions.squeeze(-1),
                    batch["reward"],
                    batch["terminated"],
                    batch["gamma"],
                )

            pred_sa = gather_q_values(q_values, batch["action"])
            loss, info_dict = mse_loss(pred_sa, td_target)
            loss = loss.mean()
            losses.append(loss.item())

            optimizer = apply_gradients(optimizer, loss)

            if step % 1000 == 0:
                print(
                    f"Step: {step}/{MAX_STEPS} | Loss: {loss.item():.4f} | Epsilon: {current_epsilon:.3f} | Buffer: {buffer_state.size}"
                )

        if step % TARGET_NET_UPDATE_FREQ == 0:
            hard_update_target_network(model, target_model)

    print("Training Complete!")
    return model, episode_returns, losses, epsilons


def evaluate_model(model, env, seed=SEED):
    print("\n" + "=" * 50)
    print("Evaluating Trained DQN Agent...")
    print("=" * 50)

    device = torch.device("cpu")
    obs, info = env.reset(seed=seed)
    total_reward = 0.0
    steps = 0

    while True:
        with torch.inference_mode():
            obs_tensor = to_tensor(obs[None, ...], device=device)

            # FIX: Get and apply the mask during evaluation
            mask_np = env.action_masks()
            mask_tensor = to_tensor(mask_np[None, ...], dtype=torch.bool, device=device)

            q_values = model(obs_tensor)
            q_values = apply_action_mask(
                q_values, mask_tensor
            )  # Prevent choosing invalid actions

            action_tensor, _ = argmax_selector(q_values)
            action = to_numpy_action(action_tensor)
            action_int = int(action.item())

        obs, reward, terminated, truncated, info = env.step(action_int)
        total_reward += reward
        steps += 1

        if terminated or truncated:
            break

    print(f"\nDQN Evaluation finished after {steps} steps.")
    print(f"Total Accumulated Reward: {total_reward:.2f}")
    env.sim.print_statistics()
    return env.sim


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
        # NOTE: We include the warming period in this throughput calculation unconditionally
        # rather than subtracting `ore_to_be_extracted_during_warming_period`.
        # This prevents massive negative throughput statistics if an agent (like a failing RL policy)
        # fails to extract enough ore to actually trigger the end of the warming phase.
        return sim.plant.ore_extraction.value / active_time
    return 0.0


if __name__ == "__main__":
    from random_baseline import run_handcoded_policy, run_random_policy
    import matplotlib.pyplot as plt
    from example_mine import MineMode

    config = MiningDRSConfig(
        replication_length=30000.0,
    )

    env = MineEnv(config=config)

    # Train
    trained_model, episode_returns, losses, epsilons = run_dqn_training(
        env, config, seed=SEED
    )

    # Evaluate DQN
    eval_env = MineEnv(config=config)
    dqn_sim = evaluate_model(trained_model, eval_env, seed=SEED)

    # Run Baselines
    handcoded_sim = run_handcoded_policy(config)
    random_sim = run_random_policy(config)

    print("\n" + "=" * 50)
    print("Comparison Summary")
    print("=" * 50)

    hc_throughput = get_throughput(handcoded_sim)
    rand_throughput = get_throughput(random_sim)
    dqn_throughput = get_throughput(dqn_sim)

    print(f"Handcoded Policy Throughput: {hc_throughput:.4f} tons/day")
    print(f"Random Baseline Throughput:  {rand_throughput:.4f} tons/day")
    print(f"DQN Agent Throughput:        {dqn_throughput:.4f} tons/day")

    print("\nGenerating side-by-side plots...")

    df_hc = handcoded_sim.telemetry.to_dataframe()
    df_rand = random_sim.telemetry.to_dataframe()
    df_dqn = dqn_sim.telemetry.to_dataframe()

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
    df_dqn = prepare_df(df_dqn)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Ore Levels
    axes[0].plot(df_hc.index, df_hc["Ore 1 Stockpile Level"], label="HC Ore 1", linestyle="--", color="blue")
    axes[0].plot(df_hc.index, df_hc["Ore 2 Stockpile Level"], label="HC Ore 2", linestyle="--", color="red")
    
    axes[0].plot(df_dqn.index, df_dqn["Ore 1 Stockpile Level"], label="DQN Ore 1", color="blue")
    axes[0].plot(df_dqn.index, df_dqn["Ore 2 Stockpile Level"], label="DQN Ore 2", color="red")
    
    axes[0].set_title("Ore 1 & 2 Stockpile Levels")
    axes[0].set_ylabel("Ore Level (Thousands of Tons)")
    axes[0].legend()

    # Modes DQN
    axes[1].step(df_dqn.index, df_dqn["Mode A"], label="Mode A", where="post")
    axes[1].step(df_dqn.index, df_dqn["Mode B"], label="Mode B", where="post")
    axes[1].step(df_dqn.index, df_dqn["Shutdown"], label="Shutdown", where="post")
    axes[1].set_title("DQN Agent: Modes")
    axes[1].set_ylabel("Mode State")
    axes[1].set_ylim(0, 4)
    axes[1].legend()

    # Modes Handcoded
    axes[2].step(df_hc.index, df_hc["Mode A"], label="Mode A", where="post")
    axes[2].step(df_hc.index, df_hc["Mode B"], label="Mode B", where="post")
    axes[2].step(df_hc.index, df_hc["Shutdown"], label="Shutdown", where="post")
    axes[2].set_title("Handcoded Policy: Modes")
    axes[2].set_ylim(0, 4)
    axes[2].legend()

    fig.tight_layout()
    fig.savefig(os.path.join(os.path.dirname(__file__), "DQN_Comparison.png"))

    # Plot Training Metrics (W&B equivalents)
    fig_metrics, axes_metrics = plt.subplots(1, 3, figsize=(18, 5))

    # 1. Episode Returns
    axes_metrics[0].plot(episode_returns)
    axes_metrics[0].set_title("DQN Episode Returns")
    axes_metrics[0].set_xlabel("Episode")
    axes_metrics[0].set_ylabel("Return")
    axes_metrics[0].grid(True, alpha=0.3)

    # 2. Training Loss
    axes_metrics[1].plot(losses, color="orange", alpha=0.6)
    axes_metrics[1].set_title("DQN Training Loss")
    axes_metrics[1].set_xlabel("Update Step")
    axes_metrics[1].set_ylabel("MSE Loss")
    axes_metrics[1].grid(True, alpha=0.3)

    # 3. Epsilon Decay
    axes_metrics[2].plot(epsilons, color="green", linewidth=2)
    axes_metrics[2].set_title("Epsilon Decay")
    axes_metrics[2].set_xlabel("Environment Step")
    axes_metrics[2].set_ylabel("Epsilon")
    axes_metrics[2].grid(True, alpha=0.3)

    fig_metrics.tight_layout()
    fig_metrics.savefig(
        os.path.join(os.path.dirname(__file__), "DQN_Training_Returns.png")
    )
    plt.close(fig_metrics)

    print(f"Plots saved to {os.path.dirname(__file__)}")
