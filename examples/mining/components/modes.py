from abc import ABC, abstractmethod
from typing import Optional, Union
from drs.module import drs
from .data import TargetRates

class RequireDecision(Exception):
    """A signal flag and engine interrupt for when the simulation requires external control."""

    pass


class OperatingMode(ABC):
    def __eq__(self, other):
        if not isinstance(other, OperatingMode):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    @property
    @abstractmethod
    def id(self) -> int:
        """The discrete integer action for the Gym environment."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """String representation for plotting/telemetry."""
        pass

    @abstractmethod
    def is_valid_start(self, model: drs.Module) -> bool:
        """Do the conditions of our system allow for this mode to be entered?
        Useful for Action Masking: Can the RL agent choose this mode right now?
        """
        pass

    @abstractmethod
    def check_end_conditions(
        self, model: drs.Module
    ) -> Union[Optional["OperatingMode"], RequireDecision]:
        """Preemption: Does the current state force a transition to a different mode? Does it require a decision from a controller as to our next mode?"""
        pass

    @abstractmethod
    def get_target_rates(self, model: drs.Module) -> TargetRates:
        """Physics: Returns the target rates (TargetRates dataclass) for this specific mode."""
        pass

class ModeA(OperatingMode):
    @property
    def id(self):
        return 0

    @property
    def name(self):
        return "MODE_A"

    def is_valid_start(self, model: drs.Module) -> bool:
        plant = model.plant
        sensors = model.sensors
        return sensors.belief_ore2_stock.value >= plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeAMineSurging()

        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeAContingency()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_a_ore1_milling_rate
        milling_2 = c.mode_a_ore2_milling_rate
        
        # Fleet provides exactly what gets used
        return TargetRates(
            extraction_rate=(milling_1 + milling_2), 
            ore1_milling_rate=milling_1, 
            ore2_milling_rate=milling_2
        )


class ModeAContingency(OperatingMode):
    @property
    def id(self):
        return 1

    @property
    def name(self):
        return "MODE_A_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeAMineSurging()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        r = c.mode_a_contingency_ore1_milling_rate
        
        # Fleet slows down to exactly match the throttled plant
        return TargetRates(
            extraction_rate=r, 
            ore1_milling_rate=r, 
            ore2_milling_rate=0.0
        )


class ModeAMineSurging(OperatingMode):
    @property
    def id(self):
        return 2

    @property
    def name(self):
        return "MODE_A_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        # Set threshold to tell engine exactly when to stop time!
        sensors.belief_ore_stock.lower_threshold = plant.config.target_ore_stock_level

        # End Surging only when the excess inventory is successfully burned off
        if sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level + 1e-6:
            return RequireDecision()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_a_ore1_milling_rate
        milling_2 = c.mode_a_ore2_milling_rate
        
        p = model.sensors.belief_routing_fraction
        # Mine extracts EXACTLY enough total rock to yield the required Ore 1
        extraction = (milling_1 / (1.0 - p)) if (1.0 - p) > 0 else 0.0
        
        return TargetRates(
            extraction_rate=extraction,
            ore1_milling_rate=milling_1,
            ore2_milling_rate=milling_2,
        )


class ModeB(OperatingMode):
    @property
    def id(self):
        return 3

    @property
    def name(self):
        return "MODE_B"

    def is_valid_start(self, model: drs.Module) -> bool:
        plant = model.plant
        sensors = model.sensors
        return sensors.belief_ore2_stock.value < plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeBContingency()

        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeBMineSurging()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_b_ore1_milling_rate
        milling_2 = c.mode_b_ore2_milling_rate
        
        # Fleet provides exactly what gets used
        return TargetRates(
            extraction_rate=(milling_1 + milling_2), 
            ore1_milling_rate=milling_1, 
            ore2_milling_rate=milling_2
        )


class ModeBContingency(OperatingMode):
    @property
    def id(self):
        return 4

    @property
    def name(self):
        return "MODE_B_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeBMineSurging()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        r = c.mode_b_contingency_ore2_milling_rate
        
        # Fleet slows down to exactly match the throttled plant
        return TargetRates(
            extraction_rate=r, 
            ore1_milling_rate=0.0, 
            ore2_milling_rate=r
        )


class ModeBMineSurging(OperatingMode):
    @property
    def id(self):
        return 5

    @property
    def name(self):
        return "MODE_B_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        # Set threshold to tell engine exactly when to stop time!
        sensors.belief_ore_stock.lower_threshold = plant.config.target_ore_stock_level

        # End Surging only when the excess inventory is successfully burned off
        if sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level + 1e-6:
            return RequireDecision()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_b_ore1_milling_rate
        milling_2 = c.mode_b_ore2_milling_rate
        
        p = model.sensors.belief_routing_fraction
        # Mine extracts EXACTLY enough total rock to yield the required Ore 2
        extraction = (milling_2 / p) if p > 0 else 0.0
        
        return TargetRates(
            extraction_rate=extraction,
            ore1_milling_rate=milling_1,
            ore2_milling_rate=milling_2,
        )


class Shutdown(OperatingMode):
    @property
    def id(self):
        return 6

    @property
    def name(self):
        return "SHUTDOWN"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        controller = model.controller
        if controller.is_campaign_complete():
            return RequireDecision()
        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        return TargetRates(
            extraction_rate=0.0, ore1_milling_rate=0.0, ore2_milling_rate=0.0
        )


class ModeC(OperatingMode):
    @property
    def id(self):
        return 7

    @property
    def name(self):
        return "MODE_C"

    def is_valid_start(self, model: drs.Module) -> bool:
        plant = model.plant
        sensors = model.sensors
        return sensors.belief_ore2_stock.value >= plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeCMineSurging()

        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeCContingency()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_c_ore1_milling_rate
        milling_2 = c.mode_c_ore2_milling_rate
        
        # Fleet provides exactly what gets used
        return TargetRates(
            extraction_rate=(milling_1 + milling_2), 
            ore1_milling_rate=milling_1, 
            ore2_milling_rate=milling_2
        )


class ModeCContingency(OperatingMode):
    @property
    def id(self):
        return 8

    @property
    def name(self):
        return "MODE_C_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeCMineSurging()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        r = c.mode_c_contingency_ore1_milling_rate
        
        # Fleet slows down to exactly match the throttled plant
        return TargetRates(
            extraction_rate=r, 
            ore1_milling_rate=r, 
            ore2_milling_rate=0.0
        )


class ModeCMineSurging(OperatingMode):
    @property
    def id(self):
        return 9

    @property
    def name(self):
        return "MODE_C_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeCContingency()

        # Set threshold to tell engine exactly when to stop time!
        sensors.belief_ore_stock.lower_threshold = plant.config.target_ore_stock_level

        # End Surging only when the excess inventory is successfully burned off
        if sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level + 1e-6:
            return RequireDecision()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_c_ore1_milling_rate
        milling_2 = c.mode_c_ore2_milling_rate
        
        p = model.sensors.belief_routing_fraction
        # Mine extracts EXACTLY enough total rock to yield the required Ore 1
        extraction = (milling_1 / (1.0 - p)) if (1.0 - p) > 0 else 0.0
        
        return TargetRates(
            extraction_rate=extraction,
            ore1_milling_rate=milling_1,
            ore2_milling_rate=milling_2,
        )


class ModeD(OperatingMode):
    @property
    def id(self):
        return 10

    @property
    def name(self):
        return "MODE_D"

    def is_valid_start(self, model: drs.Module) -> bool:
        plant = model.plant
        sensors = model.sensors
        return sensors.belief_ore2_stock.value < plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeDContingency()

        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeDMineSurging()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_d_ore1_milling_rate
        milling_2 = c.mode_d_ore2_milling_rate
        
        # Fleet provides exactly what gets used
        return TargetRates(
            extraction_rate=(milling_1 + milling_2), 
            ore1_milling_rate=milling_1, 
            ore2_milling_rate=milling_2
        )


class ModeDContingency(OperatingMode):
    @property
    def id(self):
        return 11

    @property
    def name(self):
        return "MODE_D_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeDMineSurging()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        r = c.mode_d_contingency_ore2_milling_rate
        
        # Fleet slows down to exactly match the throttled plant
        return TargetRates(
            extraction_rate=r, 
            ore1_milling_rate=0.0, 
            ore2_milling_rate=r
        )


class ModeDMineSurging(OperatingMode):
    @property
    def id(self):
        return 12

    @property
    def name(self):
        return "MODE_D_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeDContingency()

        # Set threshold to tell engine exactly when to stop time!
        sensors.belief_ore_stock.lower_threshold = plant.config.target_ore_stock_level

        # End Surging only when the excess inventory is successfully burned off
        if sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level + 1e-6:
            return RequireDecision()

        return None

    def get_target_rates(self, model: drs.Module) -> TargetRates:
        c = model.plant.config
        milling_1 = c.mode_d_ore1_milling_rate
        milling_2 = c.mode_d_ore2_milling_rate
        
        p = model.sensors.belief_routing_fraction
        # Mine extracts EXACTLY enough total rock to yield the required Ore 2
        extraction = (milling_2 / p) if p > 0 else 0.0
        
        return TargetRates(
            extraction_rate=extraction,
            ore1_milling_rate=milling_1,
            ore2_milling_rate=milling_2,
        )
