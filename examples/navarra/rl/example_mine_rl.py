# NOTE: NOT FOR USE but kept for the comments. remove when all comments in this file have been addressed.
# TODO: an example with an RL based controller using traditional RL
# TODO: fixed model, vs continually learning model.
# TODO: after that an example with an RL based controller using stream RL
# TODO: a non stationary mine with both.
# TODO: non stationary stream RL

# NOTE: there are likely several possibilities:
# 1. Fixed pretrained model. DQN and PPO
# 2. Continual learning model, still with traditional RL and batches. DQN and PPO
# 3. Continual learning model, with stream RL. Stream AC and Stream DQN
# - Non stationary mine -
# 4. Add a non stationary model using CBP and IDBD methods
# 5. POMDP versions of each (add an LSTM)
# 6. Future work.
#    a. Search (MuZero)
#    b. GVFs
#    c. Options?
#    d. Sim to Real?
#    e. Other?

# For these models some envs/things to test
# 1. how do they perform initially
# 2. how long do they take to reach a good performance
# 3. can they learn offline (ie while they get good can they train of the normal operations of the mine)
# 4. with the non-stationary environment
# 5. with a POMDP formulation
# 6. with discrete vs continuous control (high vs low level)
# 7. with different reward functions
# 8. Semi MDP vs MDP formulation
# 9. Future work:
#    a. GVFs and World Models/Search (how well can the model learn a simulator, how well can it get to the real world or simulator?), what can it learn well?
#    b. Options (can the agent learn options? or in other words its own threshholds for the Semi MDP instead of using our Semi MDP formulation that is hardcoded? are these better?)


# TODO: there are likely some constraints we should add to the system. things like stockpile limits and stuff. like you cant store infinite ore.

# TODO: what should actions be? control variables/params? There are two: the overall mine mode and the control parameters. one is discrete control and one is continuous control.
# discrete generally easier and better to start from something like:
# MineMode = {
#     HIGH_THROUGHPUT,
#     BALANCED,
#     ORE1_PRIORITY,
#     ORE2_PRIORITY,
#     RECOVERY,
#     MAINTENANCE_SAFE,
# }

# The existing plant logic implements the low-level rates.
# TODO: what should reward be? throughput? target ore levels? other metrics? a combination? make reward a configurable multi objective function. allow for abilations on the reward function. unfortunately this means reward shaping :(
# TODO: is time a desired thing to minimize? ie minimize the time to reach our termination condition?
# TODO: what is an observation? what should be available to the agent and what should be learned? will likely need to make this partially observable and so will need to include LSTMs.
# A. Fully observable baseline
# inventories
# active mode
# rates
# blend composition
# B. Realistic partial observability
# Hide:
# future ore composition
# latent degradation
# exact process rates
# future parcel arrivals
# Expose only sensor-like quantities:
# delayed measurements
# noisy assays
# conveyor readings
# stockpile estimates
# This becomes a POMDP.
# TODO: i am using a Semi MDP but could also test with a standard MDP (ie fixed time steps).
# TODO: is there the possibility of learning the thresholds and stuff using options? like to learn the Semi MDP instead of enforcing it like we are doing now? this would also mean learning continuation prob/discount factor and stuff right?

import sys
import os

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "navarra/standard"))
)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Optional

from mining_drs.engine import DRSEngine
from example_mine import MineMode, ExampleMineModel
from mine_config import MiningDRSConfig


class MineEnv(gym.Env):
    """
    OpenAI Gymnasium environment wrapping the continuous/discrete rate simulation of the mine.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        config: Optional[MiningDRSConfig] = None,
        allowed_modes: Optional[list[MineMode]] = None,
    ):
        super().__init__()

        # NOTE/TODO: Test with fixed time horizons in the future.
        # Currently, the environment uses variable time horizons (advances exactly to the next DRS event).

        # NOTE/TODO: Test both only high level and all 7 modes.
        # The user can select what actions are allowed via `allowed_modes`.

        if config is None:
            config = MiningDRSConfig()
        self.config = config

        if allowed_modes is None:
            self.allowed_modes = list(MineMode)
        else:
            self.allowed_modes = allowed_modes

        # Action space: Discrete, corresponding to the allowed modes
        self.action_space = spaces.Discrete(len(self.allowed_modes))

        # Observation space:
        # [ore_extraction, ore_stock, ore1_stock, ore2_stock, mass_of_current_parcel, percentage_of_ore2]
        high = np.array(
            [np.inf, np.inf, np.inf, np.inf, np.inf, 100.0], dtype=np.float32
        )
        low = np.zeros(6, dtype=np.float32)
        self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)

        self.sim = None
        self.engine = None

    def _get_obs(self):
        plant = self.sim.plant
        return np.array(
            [
                plant.ore_extraction.value,
                plant.ore_stock.value,
                plant.ore1_stock.value,
                plant.ore2_stock.value,
                plant.mass_of_current_parcel,
                plant.percentage_of_ore2,
            ],
            dtype=np.float32,
        )

    def _get_info(self):
        return {
            "current_mode": self.sim.controller.current_mode.value.name,
            "current_time": self.engine.current_time,
        }

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Reset simulation
        self.sim = ExampleMineModel(self.config)
        self.engine = DRSEngine(self.sim)

        # Initialize state via standard OO contract
        self.sim.initialize_state()

        return self._get_obs(), self._get_info()

    def step(self, action):
        # Decode action to mode
        chosen_mode = self.allowed_modes[action]

        # Set mode in controller
        self.sim.controller.current_mode.value = chosen_mode

        # Step the simulation to the NEXT event (Variable time horizon)
        # 1. Ask the model to set its current rates based on its state
        self.sim.zero_rates()
        self.sim.update_rates()

        # 2. Look at all variables to find the closest threshold
        current_variables = list(self.sim.variables())
        dt, trigger_var, is_upper = self.engine.calculate_min_dt(current_variables)

        if dt < 0:
            raise ValueError("Time delta (dt) cannot be negative.")

        # 3. Advance time
        self.engine.current_time += dt
        for var in current_variables:
            var.update(dt)

        # 4. Ask the model if any discrete transitions trigger
        self.sim.check_transitions(trigger_var, is_upper)

        # 5. Record statistics
        self.sim.record_statistics(self.engine.current_time)

        # Determine termination
        terminated = self.sim.is_terminating_condition_met()
        # Ensure we also terminate if max_time is reached (if applicable)
        truncated = self.engine.current_time >= self.config.replication_length

        # NOTE/TODO: Review this and come up with different reward functions with Navarra.
        # Current naive reward: throughput over this dt, minus penalty for stock deviation.
        reward = 0.0
        if dt > 0:
            extraction_rate = self.sim.plant.ore_extraction.rate
            stock_deviation = abs(
                self.sim.plant.ore_stock.value - self.config.target_ore_stock_level
            )

            throughput_reward = extraction_rate * dt
            penalty = stock_deviation * dt * 0.1  # Arbitrary penalty scale

            reward = throughput_reward - penalty

        if terminated:
            reward += 10000.0  # Completion bonus

        return self._get_obs(), float(reward), terminated, truncated, self._get_info()

    def render(self):
        pass


if __name__ == "__main__":
    from gymnasium.utils.env_checker import check_env

    # Test with default config
    env = MineEnv()

    print("Checking environment with gymnasium env_checker...")
    check_env(env)
    print("Environment check passed!")

    print("\nRunning a random agent for 10 steps...")
    obs, info = env.reset()
    for i in range(10):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        print(
            f"Step {i+1} | Action: {env.allowed_modes[action].name} | Reward: {reward:.2f} | Mode: {info['current_mode']} | Time: {info['current_time']:.2f}"
        )
        if terminated or truncated:
            print("Episode finished early!")
            break
