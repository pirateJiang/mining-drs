import sys
import os
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import wandb
from tensordict import TensorDict
from typing import Tuple, Callable
from collections import deque
from functools import partial

# Add rl-stuff to path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../rl-stuff"))
)

from functional.initialization import set_seed
from functional.replay_buffer import (
    init_per_buffer,
    sample_per,
    update_priorities,
    circular_write_strategy,
    with_per_tracking,
)
from functional.losses import with_per_weights, cross_entropy_loss
from functional.td import compute_categorical_q_td_target
from functional.action_selection import (
    argmax_selector,
    expected_value,
    gather_q_values,
    apply_action_mask,
)
from functional.schedules import get_linear_schedule
from functional.optimizer import apply_gradients
from functional.network import hard_update_target_network
from functional.utils import (
    to_tensor,
    to_numpy_action,
)
from networks.noisy_linear import NoisyLinear

# Add standard example directory to path to import mine models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../standard")))

from env import MineEnv
from mine_config import MiningDRSConfig

# --- Constants ---
BATCH_SIZE = 128
GAMMA = 0.99
LEARNING_RATE = 1e-3  
MAX_STEPS = 100_000
UPDATE_FREQ = 4
BUFFER_CAPACITY = 50000
MIN_BUFFER_SIZE = 1000  # Warmup phase!
TARGET_NET_UPDATE_FREQ = 100
SEED = 42

# PER Constants
ALPHA = 0.6
BETA_START = 0.4
BETA_FRAMES = 100_000

# Distributional (C51) Constants
V_MIN = -50.0
V_MAX = 100.0  
ATOM_SIZE = 51

# Multi-step
N_STEPS = 3


def make_smdp_n_step_accumulator(n_steps: int) -> Callable:
    """
    Custom N-step accumulator for SMDP.
    Instead of multiplying by a constant GAMMA, it geometrically accumulates 
    using the exact smdp_gamma (gamma^dt) for each transition.
    """
    history = deque(maxlen=n_steps)

    def process_transition(
        obs: torch.Tensor,
        action: torch.Tensor,
        reward: torch.Tensor,
        next_obs: torch.Tensor,
        terminated: torch.Tensor,
        truncated: torch.Tensor,
        smdp_gamma: torch.Tensor,
        mask: torch.Tensor,
        next_mask: torch.Tensor,
    ) -> TensorDict:
        ready_transitions = []
        is_done = terminated.item() or truncated.item()

        history.append((
            obs.detach(),
            action.detach(),
            reward.item(),
            next_obs.detach(),
            terminated.item(),
            truncated.item(),
            smdp_gamma.item(),
            mask.detach(),
            next_mask.detach(),
        ))

        if len(history) == n_steps and not is_done:
            n_step_reward = 0.0
            cumulative_gamma = 1.0
            for trans in history:
                n_step_reward += trans[2] * cumulative_gamma
                cumulative_gamma *= trans[6]

            first_obs, first_act, _, _, _, _, _, first_mask, _ = history[0]
            _, _, _, final_next_obs, final_term, final_trunc, _, _, final_next_mask = history[-1]

            ready_transitions.append({
                "obs": first_obs,
                "action": first_act,
                "reward": torch.tensor(n_step_reward, dtype=torch.float32),
                "next_obs": final_next_obs,
                "terminated": torch.tensor(final_term, dtype=torch.bool),
                "truncated": torch.tensor(final_trunc, dtype=torch.bool),
                "gamma": torch.tensor(cumulative_gamma, dtype=torch.float32),
                "mask": first_mask,
                "next_mask": final_next_mask,
            })
            history.popleft()

        elif is_done:
            while history:
                n_step_reward = 0.0
                cumulative_gamma = 1.0
                for trans in history:
                    n_step_reward += trans[2] * cumulative_gamma
                    cumulative_gamma *= trans[6]

                first_obs, first_act, _, _, _, _, _, first_mask, _ = history[0]
                _, _, _, final_next_obs, final_term, final_trunc, _, _, final_next_mask = history[-1]

                ready_transitions.append({
                    "obs": first_obs,
                    "action": first_act,
                    "reward": torch.tensor(n_step_reward, dtype=torch.float32),
                    "next_obs": final_next_obs,
                    "terminated": torch.tensor(final_term, dtype=torch.bool),
                    "truncated": torch.tensor(final_trunc, dtype=torch.bool),
                    "gamma": torch.tensor(cumulative_gamma, dtype=torch.float32),
                    "mask": first_mask,
                    "next_mask": final_next_mask,
                })
                history.popleft()

        if ready_transitions:
            stacked = {
                k: torch.stack([t[k] for t in ready_transitions])
                for k in ready_transitions[0].keys()
            }
            return TensorDict(stacked, batch_size=[len(ready_transitions)])
        
        return TensorDict({}, batch_size=[0])

    def reset():
        history.clear()

    return process_transition, reset


class RainbowNetwork(nn.Module):
    def __init__(self, input_shape: Tuple, num_actions: int, atom_size: int = 51):
        super().__init__()
        self.input_shape = input_shape
        self.num_actions = num_actions
        self.atom_size = atom_size
        
        in_features = input_shape[0] if isinstance(input_shape, tuple) else input_shape

        self.feature_layer = NoisyLinear(in_features, 512)

        self.advantage_head = nn.Sequential(
            NoisyLinear(512, 512),
            nn.ReLU(),
            NoisyLinear(512, num_actions * atom_size),
        )
        self.value_head = nn.Sequential(
            NoisyLinear(512, 512),
            nn.ReLU(),
            NoisyLinear(512, atom_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.feature_layer(x))

        advantage = self.advantage_head(x).view(-1, self.num_actions, self.atom_size)
        value = self.value_head(x).view(-1, 1, self.atom_size)

        # Dueling combination for distributional RL
        q_atoms = value + advantage - advantage.mean(dim=1, keepdim=True)
        return q_atoms

    def reset_noise(self):
        for module in self.modules():
            if isinstance(module, NoisyLinear):
                module.reset_noise()


def run_rainbow_training(env, config, seed=SEED):
    set_seed(seed)
    
    obs_shape = env.observation_space.shape
    num_actions = env.action_space.n
    device = torch.device("cpu")
    support = torch.linspace(V_MIN, V_MAX, ATOM_SIZE).to(device)

    model = RainbowNetwork(obs_shape, num_actions, ATOM_SIZE).to(device)
    target_model = RainbowNetwork(obs_shape, num_actions, ATOM_SIZE).to(device)
    target_model.load_state_dict(model.state_dict())

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    buffer_state = init_per_buffer(
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
    per_add_transition = with_per_tracking(circular_write_strategy)

    accumulate_smdp_n_step, reset_accumulator = make_smdp_n_step_accumulator(n_steps=N_STEPS)

    obs, info = env.reset(seed=seed)
    rng_key = torch.Generator(device=device)
    rng_key.manual_seed(seed)

    wandb.init(
        project="rainbow-mine-env",
        mode="disabled",
        config={
            "batch_size": BATCH_SIZE,
            "gamma": GAMMA,
            "learning_rate": LEARNING_RATE,
            "buffer_capacity": BUFFER_CAPACITY,
            "n_steps": N_STEPS,
            "atom_size": ATOM_SIZE,
            "v_min": V_MIN,
            "v_max": V_MAX,
        },
    )

    print("=" * 50)
    print("Starting Rainbow DQN Training...")
    print("=" * 50)

    episode_returns = []
    losses = []
    current_return = 0.0

    for step in range(MAX_STEPS):
        with torch.inference_mode():
            mask_np = env.action_masks()
            mask_tensor = to_tensor(mask_np[None, ...], dtype=torch.bool, device=device)

            obs_tensor = to_tensor(obs[None, ...], device=device)
            
            # 1. Resample noise for the actor (replaces epsilon-greedy exploration)
            model.reset_noise()
            
            predictions = model(obs_tensor)
            
            # Extract expected Q values from C51 atoms
            expected_qs = expected_value(predictions, support=support)
            
            # Apply SMDP Action Masking
            expected_qs = apply_action_mask(expected_qs, mask_tensor)
            
            action, _ = argmax_selector(expected_qs)
            action_np = to_numpy_action(action)
            action_int = int(action_np.item())

        next_obs, reward, terminated, truncated, info = env.step(action_int)

        dt = info.get("time_elapsed", 1.0)
        smdp_gamma = GAMMA**dt
        next_mask_np = env.action_masks()

        # Accumulate SMDP N-Step
        n_step_transitions = accumulate_smdp_n_step(
            to_tensor(obs),
            action.squeeze(0).detach().to(torch.long),
            to_tensor(reward, dtype=torch.float32),
            to_tensor(next_obs),
            to_tensor(terminated, dtype=torch.bool),
            to_tensor(truncated, dtype=torch.bool),
            to_tensor(smdp_gamma, dtype=torch.float32),
            mask_tensor.squeeze(0),
            to_tensor(next_mask_np, dtype=torch.bool, device=device),
        )

        if n_step_transitions.batch_size[0] > 0:
            buffer_state = per_add_transition(buffer_state, n_step_transitions)

        current_return += reward
        obs = next_obs

        if terminated or truncated:
            episode_returns.append(current_return)
            current_return = 0.0
            obs, info = env.reset()
            reset_accumulator()

        if step > MIN_BUFFER_SIZE and step % UPDATE_FREQ == 0:
            beta = get_linear_schedule(step, BETA_START, 1.0, BETA_FRAMES)
            beta_tensor = torch.tensor(beta, dtype=torch.float32, device=device)

            batch, tree_indices, is_weights = sample_per(
                buffer_state, BATCH_SIZE, beta=beta_tensor
            )

            # Resample noise for training step
            model.reset_noise()
            target_model.reset_noise()

            # Forward passes
            logits = model(batch["obs"])
            with torch.no_grad():
                next_logits_online = model(batch["next_obs"])
                next_logits_target = target_model(batch["next_obs"])

                next_expected_qs = expected_value(next_logits_online, support=support)
                
                # Apply next-action mask to prevent target hallucination!
                next_expected_qs = apply_action_mask(next_expected_qs, batch["next_mask"])
                next_actions, _ = argmax_selector(next_expected_qs)

                td_target = compute_categorical_q_td_target(
                    next_logits_target,
                    next_actions.squeeze(-1),
                    batch["reward"],
                    batch["terminated"],
                    batch["gamma"],
                    support=support,
                    v_min=V_MIN,
                    v_max=V_MAX,
                    atom_size=ATOM_SIZE,
                )

            pred_sa_logits = gather_q_values(logits, batch["action"])

            per_loss_fn = with_per_weights(cross_entropy_loss, is_weights)
            loss, info_dict = per_loss_fn(pred_sa_logits, td_target)

            optimizer = apply_gradients(optimizer, loss)

            buffer_state = update_priorities(
                buffer_state, tree_indices, info_dict["priorities"], alpha=ALPHA
            )

            losses.append(loss.item())

            if step % 1000 == 0:
                print(
                    f"Step: {step}/{MAX_STEPS} | Loss: {loss.item():.4f} | Beta: {beta:.3f} | Buffer: {buffer_state.size}"
                )

        if step % TARGET_NET_UPDATE_FREQ == 0:
            hard_update_target_network(model, target_model)

    print("Training Complete!")
    return model, episode_returns, losses


def evaluate_model(model, env, seed=SEED):
    print("\n" + "=" * 50)
    print("Evaluating Trained Rainbow DQN Agent...")
    print("=" * 50)

    device = torch.device("cpu")
    support = torch.linspace(V_MIN, V_MAX, ATOM_SIZE).to(device)
    obs, info = env.reset(seed=seed)
    total_reward = 0.0
    steps = 0

    while True:
        with torch.inference_mode():
            obs_tensor = to_tensor(obs[None, ...], device=device)

            mask_np = env.action_masks()
            mask_tensor = to_tensor(mask_np[None, ...], dtype=torch.bool, device=device)

            # In evaluation, we can disable noise. NoisyLinear layers often use fixed randomness
            # or expect `.eval()` to be called. For NoisyLinear we might just let it run or remove noise.
            # Technically, using inference_mode and not resampling noise works well, or taking mean weight.
            # By default NoisyNet uses deterministic weights if we don't resample, which acts as a valid policy.
            
            predictions = model(obs_tensor)
            expected_qs = expected_value(predictions, support=support)
            expected_qs = apply_action_mask(expected_qs, mask_tensor)

            action_tensor, _ = argmax_selector(expected_qs)
            action = to_numpy_action(action_tensor)
            action_int = int(action.item())

        obs, reward, terminated, truncated, info = env.step(action_int)
        total_reward += reward
        steps += 1

        if terminated or truncated:
            break

    print(f"\nRainbow DQN Evaluation finished after {steps} steps.")
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
    trained_model, episode_returns, losses = run_rainbow_training(
        env, config, seed=SEED
    )

    # Evaluate Rainbow DQN
    eval_env = MineEnv(config=config)
    rainbow_sim = evaluate_model(trained_model, eval_env, seed=SEED)

    # Run Baselines
    handcoded_sim = run_handcoded_policy(config)
    random_sim = run_random_policy(config)

    print("\n" + "=" * 50)
    print("Comparison Summary")
    print("=" * 50)

    hc_throughput = get_throughput(handcoded_sim)
    rand_throughput = get_throughput(random_sim)
    rainbow_throughput = get_throughput(rainbow_sim)

    print(f"Handcoded Policy Throughput:  {hc_throughput:.4f} tons/day")
    print(f"Random Baseline Throughput:   {rand_throughput:.4f} tons/day")
    print(f"Rainbow DQN Agent Throughput: {rainbow_throughput:.4f} tons/day")

    print("\nGenerating side-by-side plots...")

    df_hc = handcoded_sim.telemetry.to_dataframe()
    df_rand = random_sim.telemetry.to_dataframe()
    df_rainbow = rainbow_sim.telemetry.to_dataframe()

    def prepare_df(df):
        df["Mode A"] = df["current_mode"].apply(
            lambda m: 3 if m in (MineMode.MODE_A, MineMode.MODE_A_CONTINGENCY, MineMode.MODE_A_MINE_SURGING) else 0
        )
        df["Mode B"] = df["current_mode"].apply(
            lambda m: 2 if m in (MineMode.MODE_B, MineMode.MODE_B_CONTINGENCY, MineMode.MODE_B_MINE_SURGING) else 0
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
    df_rainbow = prepare_df(df_rainbow)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Ore Levels
    axes[0].plot(df_hc.index, df_hc["Ore 1 Stockpile Level"], label="HC Ore 1", linestyle="--", color="blue")
    axes[0].plot(df_hc.index, df_hc["Ore 2 Stockpile Level"], label="HC Ore 2", linestyle="--", color="red")
    
    axes[0].plot(df_rainbow.index, df_rainbow["Ore 1 Stockpile Level"], label="Rainbow Ore 1", color="blue")
    axes[0].plot(df_rainbow.index, df_rainbow["Ore 2 Stockpile Level"], label="Rainbow Ore 2", color="red")
    
    axes[0].set_title("Ore 1 & 2 Stockpile Levels")
    axes[0].set_ylabel("Ore Level (Thousands of Tons)")
    axes[0].legend()

    # Modes Rainbow
    axes[1].step(df_rainbow.index, df_rainbow["Mode A"], label="Mode A", where="post")
    axes[1].step(df_rainbow.index, df_rainbow["Mode B"], label="Mode B", where="post")
    axes[1].step(df_rainbow.index, df_rainbow["Shutdown"], label="Shutdown", where="post")
    axes[1].set_title("Rainbow DQN Agent: Modes")
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
    fig.savefig(os.path.join(os.path.dirname(__file__), "Rainbow_DQN_Comparison.png"))

    # Plot Training Metrics
    fig_metrics, axes_metrics = plt.subplots(1, 2, figsize=(12, 5))

    # 1. Episode Returns
    axes_metrics[0].plot(episode_returns)
    axes_metrics[0].set_title("Rainbow DQN Episode Returns")
    axes_metrics[0].set_xlabel("Episode")
    axes_metrics[0].set_ylabel("Return")
    axes_metrics[0].grid(True, alpha=0.3)

    # 2. Training Loss
    axes_metrics[1].plot(losses, color="orange", alpha=0.6)
    axes_metrics[1].set_title("Rainbow DQN Training Loss")
    axes_metrics[1].set_xlabel("Update Step")
    axes_metrics[1].set_ylabel("Cross Entropy Loss")
    axes_metrics[1].grid(True, alpha=0.3)

    fig_metrics.tight_layout()
    fig_metrics.savefig(
        os.path.join(os.path.dirname(__file__), "Rainbow_DQN_Training_Returns.png")
    )
    plt.close(fig_metrics)

    print(f"Plots saved to {os.path.dirname(__file__)}")
