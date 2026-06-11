from drs.module import drs
from examples.mining.components.modes import RequireDecision
from examples.mining.components.config import ConcentratorConfig
from examples.mining.components.sensors import ConcentratorSensorNetwork
from examples.mining.components.controllers import ConcentratorController
from examples.mining.components.modes import (
    ModeA,
    ModeB,
    ModeAMineSurging,
    ModeBMineSurging,
    Shutdown,
)

class RL_MineController(ConcentratorController):
    """A modified controller that yields to the RL agent using RequireDecision."""

    def __init__(self, config: ConcentratorConfig, sensors: ConcentratorSensorNetwork, mine, fleet, plant):
        super().__init__(config, sensors, mine, fleet, plant)
        self.pending_rl_action = None  # Stores the action passed in by env.step()

    def controller_decision(self):
        c = self.config
        sensors = self.sensors
        m = self.current_mode.value.name

        if self.is_campaign_complete():
            # --- RL INTERCEPT POINT ---
            if m == "SHUTDOWN":
                if self.pending_rl_action is not None:
                    # Apply the queued RL action
                    self.reset_campaign_timer()
                    if self.pending_rl_action == 0:
                        chosen_mode = ModeA()
                    elif self.pending_rl_action == 1:
                        chosen_mode = ModeB()
                    elif self.pending_rl_action == 2:
                        chosen_mode = ModeAMineSurging()
                    elif self.pending_rl_action == 3:
                        chosen_mode = ModeBMineSurging()
                    self.pending_rl_action = None
                    return chosen_mode
                else:
                    # Raise your existing flag to pause the DRSEngine
                    raise RequireDecision()
            else:
                self.reset_campaign_timer()
                return Shutdown()

        # Automated physical preemptions remain untouched
        if m in ("MODE_A_CONTINGENCY", "MODE_B_CONTINGENCY"):
            if self.is_contingency_complete():
                self.reset_contingency_timer()
                return ModeA() if m == "MODE_A_CONTINGENCY" else ModeB()

        if m in ("MODE_A_MINE_SURGING", "MODE_B_MINE_SURGING"):
            if sensors.belief_ore_stock.value <= c.target_ore_stock_level:
                return ModeA() if m == "MODE_A_MINE_SURGING" else ModeB()

        return None
