import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Optional
import sys
import os

# Add standard example directory to path to import mine models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../standard")))
# Add src directory to path to import mining_drs
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)

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

        # Observation space (Normalized [0, 1] approx):
        # [ore_stock_norm, ore1_stock_norm, ore2_stock_norm, mass_of_current_parcel_norm, percentage_of_ore2_norm]
        high = (
            np.ones(5, dtype=np.float32) * 5.0
        )  # Give a bit of headroom above 1.0 just in case
        low = np.zeros(5, dtype=np.float32)
        self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)

        self.sim = None
        self.engine = None

    def _get_obs(self):
        plant = self.sim.plant

        # Dynamically scale based on config thresholds!
        # Target stock is typically around 60,000, so 1.5x is a safe upper bound estimate
        MAX_STOCK = self.config.target_ore_stock_level * 1.5

        # Pull max parcel size directly from the geostatistical parameters
        MAX_PARCEL = self.config.max_ore_mass

        return np.array(
            [
                plant.ore_stock.value / MAX_STOCK,
                plant.ore1_stock.value / MAX_STOCK,
                plant.ore2_stock.value / MAX_STOCK,
                plant.mass_of_current_parcel / MAX_PARCEL,
                plant.percentage_of_ore2 / 100.0,
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

    # TODO: this should follow gym standards, and this at the moment does not.
    def action_masks(self) -> np.ndarray:
        """
        Returns a boolean array where True indicates the action is valid.
        This represents the safety PLC / interlock logic restricting operational envelopes.
        """
        masks = np.zeros(self.action_space.n, dtype=bool)

        # Save current mode to restore later
        original_mode = self.sim.controller.current_mode.value

        for action in range(self.action_space.n):
            mode = self.allowed_modes[action]

            # Temporarily set mode and check rates
            self.sim.controller.current_mode.value = mode
            self.sim.zero_rates()
            self.sim.update_rates()

            is_valid = True
            for var in self.sim.variables():
                if var.rate < 0 and var.value <= var.lower_threshold + 1e-6:
                    is_valid = False
                    break
            masks[action] = is_valid

        # Restore original mode
        self.sim.controller.current_mode.value = original_mode
        self.sim.zero_rates()
        self.sim.update_rates()

        return masks

    def step(self, action):
        # Decode action to mode
        chosen_mode = self.allowed_modes[action]

        # --- Safety PLC / Interlock ---
        # The plant refuses unsafe commands.
        masks = self.action_masks()

        if not masks[action]:
            raise ValueError(
                f"Agent attempted an illegal action {action} ({self.allowed_modes[action]}). "
                f"This means your action masking is failing to prevent invalid moves!"
            )

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

        # --- FIRST-PRINCIPLES REWARD FUNCTION ---
        # NOTE/TODO: Review this and come up with different reward functions with Navarra.
        reward = 0.0
        if dt > 0:
            # 1. The Core Economic Goal: Throughput
            # We normalize this so the max reward is 1.0.
            # TODO: change this in the future to try and not require an estimate of reward and stuff
            NOMINAL_EXTRACTION_RATE = (
                4000.0  # Estimate of the absolute max theoretical rate
            )
            extraction_rate = self.sim.plant.ore_extraction.rate

            # The base reward is just how much ore we are pushing.
            economic_reward = extraction_rate / NOMINAL_EXTRACTION_RATE

            # 2. The Buffer Constraints: Deadband Penalty
            # The stockpile is a buffer. We ONLY penalize if it gets dangerously full or empty.
            current_stock = self.sim.plant.ore_stock.value
            MAX_STOCK = 100000.0  # The physical limit
            stock_ratio = current_stock / MAX_STOCK

            health_penalty = 0.0

            # DEADBAND: No penalty between 25% and 75% capacity! Use the buffer!
            if stock_ratio < 0.25:
                # Dangerously low. Penalty scales up quadratically as it approaches 0.
                health_penalty = ((0.25 - stock_ratio) / 0.25) ** 2
            elif stock_ratio > 0.75:
                # Dangerously high. Penalty scales up quadratically as it approaches 1.0.
                health_penalty = ((stock_ratio - 0.75) / 0.25) ** 2

            # 3. Combine and Apply SMDP Time-Scaling
            # We subtract the health penalty from the economic reward.
            # If the plant is crashing, the penalty overpowers the throughput.
            instantaneous_reward = economic_reward - health_penalty

            # IMPORTANT: Bound the SMDP reward using the continuous discount integral
            # This prevents gradient explosions when dt is extremely large.
            # Ensure this matches the GAMMA in your training script!
            GAMMA_PARAM = 0.99
            reward = instantaneous_reward * (1.0 - (GAMMA_PARAM**dt))

        info = self._get_info()
        info["time_elapsed"] = dt

        return self._get_obs(), float(reward), terminated, truncated, info

    def render(self):
        pass
