from drs.modes import OperatingMode, RequireDecision
from drs.module import drs


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

        # 2. Physical Preemption: Ore 1 is empty, must surge
        if sensors.belief_ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeAMineSurging()

        # 3. Logic Preemption: Ore 2 dropped to 0, trigger contingency
        if sensors.belief_ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeAContingency()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate

        # --- Plant Rates ---
        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_a_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(c.mode_a_ore1_milling_rate)
        plant.true_ore2_stock.set_target_outflow(c.mode_a_ore2_milling_rate)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - c.mode_a_ore1_milling_rate
        sensors.belief_ore2_stock.rate = r * p - c.mode_a_ore2_milling_rate

        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0
        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_a.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )


class ModeAContingency(OperatingMode):
    @property
    def id(self):
        return 1

    @property
    def name(self):
        return "MODE_A_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
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

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_a_contingency_ore1_milling_rate

        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_a_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(r)
        plant.true_ore2_stock.set_target_outflow(0.0)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - r
        sensors.belief_ore2_stock.rate = r * p

        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0


        controller.time_mode_a_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )
        controller.time_executed_contingency.upper_threshold = (
            controller.config.duration_of_contingency_segments
        )


class ModeAMineSurging(OperatingMode):
    @property
    def id(self):
        return 2

    @property
    def name(self):
        return "MODE_A_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        # Cross-stockout physical preemption logic has been removed to match Arena behavior.

        # THE ORIGINAL ARENA FIX: 
        # Only evaluate the target floor constraint if the stockpile is actively draining (Rate < 0).
        # During mid-campaign surging, rate > 0, so this safely evaluates to False and prevents the deadlock.
        if sensors.belief_ore_stock.rate < 0 and sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_a_ore1_milling_rate * 1.0 / (1.0 - p)

        mine.true_ore_extraction.rate = r
        r_mill = c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r_mill * getattr(c, "mode_a_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r_mill
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = (
            r - c.mode_a_ore1_milling_rate - c.mode_a_ore2_milling_rate
        )
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(r * (1.0 - p))
        plant.true_ore2_stock.set_target_outflow(c.mode_a_ore2_milling_rate)

        sensors.belief_ore1_stock.rate = 0.0
        sensors.belief_ore2_stock.rate = r * p - c.mode_a_ore2_milling_rate

        plant.true_ore_stock.lower_threshold = sensors.belief_ore_stock.lower_threshold = c.target_ore_stock_level
        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_a_surging.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
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

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate

        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_b_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(c.mode_b_ore1_milling_rate)
        plant.true_ore2_stock.set_target_outflow(c.mode_b_ore2_milling_rate)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - c.mode_b_ore1_milling_rate
        sensors.belief_ore2_stock.rate = r * p - c.mode_b_ore2_milling_rate

        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0
        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_b.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )


class ModeBContingency(OperatingMode):
    @property
    def id(self):
        return 4

    @property
    def name(self):
        return "MODE_B_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
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

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_b_contingency_ore2_milling_rate

        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_b_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(0.0)
        plant.true_ore2_stock.set_target_outflow(r)

        sensors.belief_ore1_stock.rate = r * (1.0 - p)
        sensors.belief_ore2_stock.rate = r * p - r

        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_b_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )
        controller.time_executed_contingency.upper_threshold = (
            controller.config.duration_of_contingency_segments
        )


class ModeBMineSurging(OperatingMode):
    @property
    def id(self):
        return 5

    @property
    def name(self):
        return "MODE_B_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        sensors = model.sensors

        if controller.is_campaign_complete():
            return RequireDecision()

        # Cross-stockout physical preemption logic has been removed to match Arena behavior.

        # THE ORIGINAL ARENA FIX: 
        # Only evaluate the target floor constraint if the stockpile is actively draining (Rate < 0).
        # During mid-campaign surging, rate > 0, so this safely evaluates to False and prevents the deadlock.
        if sensors.belief_ore_stock.rate < 0 and sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_b_ore2_milling_rate * 1.0 / p

        mine.true_ore_extraction.rate = r
        r_mill = c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r_mill * getattr(c, "mode_b_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r_mill
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = (
            r - c.mode_b_ore1_milling_rate - c.mode_b_ore2_milling_rate
        )
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(c.mode_b_ore1_milling_rate)
        plant.true_ore2_stock.set_target_outflow(r * p)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - c.mode_b_ore1_milling_rate
        sensors.belief_ore2_stock.rate = 0.0

        plant.true_ore_stock.lower_threshold = sensors.belief_ore_stock.lower_threshold = c.target_ore_stock_level
        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0


        controller.time_mode_b_surging.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )


class Shutdown(OperatingMode):
    @property
    def id(self):
        return 6

    @property
    def name(self):
        return "SHUTDOWN"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
        return True

    def check_end_conditions(self, model: drs.Module):
        controller = model.controller
        sensors = model.sensors
        if controller.is_campaign_complete():
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        controller = model.controller
        controller.time_shutdown.rate = 1.0
        
        # Explicitly halt physical extraction and milling rates
        model.mine.true_ore_extraction.rate = 0.0
        model.mine.true_ore_extracted_from_current_parcel.rate = 0.0
        model.plant.true_ore1_stock.set_target_outflow(0.0)
        model.plant.true_ore2_stock.set_target_outflow(0.0)
        model.sensors.belief_ore1_stock.rate = 0.0
        model.sensors.belief_ore2_stock.rate = 0.0
        
        if hasattr(model.plant, "total_cyanide_consumed"):
            model.plant.true_total_cyanide_consumed.rate = 0.0
        if hasattr(model.plant, "total_ore_milled"):
            model.plant.true_total_ore_milled.rate = 0.0
            
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_shutdowns
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

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_c_ore1_milling_rate + c.mode_c_ore2_milling_rate

        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_c_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(c.mode_c_ore1_milling_rate)
        plant.true_ore2_stock.set_target_outflow(c.mode_c_ore2_milling_rate)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - c.mode_c_ore1_milling_rate
        sensors.belief_ore2_stock.rate = r * p - c.mode_c_ore2_milling_rate

        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0
        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_c.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )


class ModeCContingency(OperatingMode):
    @property
    def id(self):
        return 8

    @property
    def name(self):
        return "MODE_C_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
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

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_c_contingency_ore1_milling_rate

        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_c_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(r)
        plant.true_ore2_stock.set_target_outflow(0.0)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - r
        sensors.belief_ore2_stock.rate = r * p

        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0


        controller.time_mode_c_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )
        controller.time_executed_contingency.upper_threshold = (
            controller.config.duration_of_contingency_segments
        )


class ModeCMineSurging(OperatingMode):
    @property
    def id(self):
        return 9

    @property
    def name(self):
        return "MODE_C_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
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

        # THE ORIGINAL ARENA FIX: 
        # Only evaluate the target floor constraint if the stockpile is actively draining (Rate < 0).
        # During mid-campaign surging, rate > 0, so this safely evaluates to False and prevents the deadlock.
        if sensors.belief_ore_stock.rate < 0 and sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_c_ore1_milling_rate * 1.0 / (1.0 - p)

        mine.true_ore_extraction.rate = r
        r_mill = c.mode_c_ore1_milling_rate + c.mode_c_ore2_milling_rate
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r_mill * getattr(c, "mode_c_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r_mill
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = (
            r - c.mode_c_ore1_milling_rate - c.mode_c_ore2_milling_rate
        )
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(r * (1.0 - p))
        plant.true_ore2_stock.set_target_outflow(c.mode_c_ore2_milling_rate)

        sensors.belief_ore1_stock.rate = 0.0
        sensors.belief_ore2_stock.rate = r * p - c.mode_c_ore2_milling_rate

        plant.true_ore_stock.lower_threshold = sensors.belief_ore_stock.lower_threshold = c.target_ore_stock_level
        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_c_surging.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
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

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_d_ore1_milling_rate + c.mode_d_ore2_milling_rate

        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_d_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(c.mode_d_ore1_milling_rate)
        plant.true_ore2_stock.set_target_outflow(c.mode_d_ore2_milling_rate)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - c.mode_d_ore1_milling_rate
        sensors.belief_ore2_stock.rate = r * p - c.mode_d_ore2_milling_rate

        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0
        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_d.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )


class ModeDContingency(OperatingMode):
    @property
    def id(self):
        return 11

    @property
    def name(self):
        return "MODE_D_CONTINGENCY"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
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

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_d_contingency_ore2_milling_rate

        mine.true_ore_extraction.rate = r
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r * getattr(c, "mode_d_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = 0.0
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(0.0)
        plant.true_ore2_stock.set_target_outflow(r)

        sensors.belief_ore1_stock.rate = r * (1.0 - p)
        sensors.belief_ore2_stock.rate = r * p - r

        plant.true_ore2_stock.mass.lower_threshold = sensors.belief_ore2_stock.lower_threshold = 0.0


        controller.time_mode_d_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_contingency.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )
        controller.time_executed_contingency.upper_threshold = (
            controller.config.duration_of_contingency_segments
        )


class ModeDMineSurging(OperatingMode):
    @property
    def id(self):
        return 12

    @property
    def name(self):
        return "MODE_D_MINE_SURGING"

    def is_valid_start(self, model: drs.Module) -> bool:
        sensors = model.sensors
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

        # THE ORIGINAL ARENA FIX: 
        # Only evaluate the target floor constraint if the stockpile is actively draining (Rate < 0).
        # During mid-campaign surging, rate > 0, so this safely evaluates to False and prevents the deadlock.
        if sensors.belief_ore_stock.rate < 0 and sensors.belief_ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config
        mine = model.mine
        fleet = model.fleet
        sensors = model.sensors

        p = model.sensors.belief_routing_fraction
        r = c.mode_d_ore2_milling_rate * 1.0 / p

        mine.true_ore_extraction.rate = r
        r_mill = c.mode_d_ore1_milling_rate + c.mode_d_ore2_milling_rate
        if hasattr(plant, "true_total_cyanide_consumed"):
            plant.true_total_cyanide_consumed.rate = r_mill * getattr(c, "mode_d_avg_cyanide", 0.0)
        if hasattr(plant, "true_total_ore_milled"):
            plant.true_total_ore_milled.rate = r_mill
        mine.true_ore_extracted_from_current_parcel.rate = r
        plant.true_ore_stock.rate = sensors.belief_ore_stock.rate = (
            r - c.mode_d_ore1_milling_rate - c.mode_d_ore2_milling_rate
        )
        # 1. Set the Fleet Routing Policy
        fleet.fraction_to_ore2 = p
        
        # 2. Set the requested Outflow for the Mill 
        plant.true_ore1_stock.set_target_outflow(c.mode_d_ore1_milling_rate)
        plant.true_ore2_stock.set_target_outflow(r * p)

        sensors.belief_ore1_stock.rate = r * (1.0 - p) - c.mode_d_ore1_milling_rate
        sensors.belief_ore2_stock.rate = 0.0

        plant.true_ore_stock.lower_threshold = sensors.belief_ore_stock.lower_threshold = c.target_ore_stock_level
        plant.true_ore1_stock.mass.lower_threshold = sensors.belief_ore1_stock.lower_threshold = 0.0


        controller.time_mode_d_surging.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )
