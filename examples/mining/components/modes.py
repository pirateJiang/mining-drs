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
        return plant.ore2_stock.value >= plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        # 2. Physical Preemption: Ore 1 is empty, must surge
        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeAMineSurging()

        # 3. Logic Preemption: Ore 2 dropped to 0, trigger contingency
        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeAContingency()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate

        # --- Plant Rates ---
        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_a_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p) - c.mode_a_ore1_milling_rate
        plant.ore2_stock.rate = r * p - c.mode_a_ore2_milling_rate

        plant.ore1_stock.lower_threshold = 0.0
        plant.ore2_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeAMineSurging()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_a_contingency_ore1_milling_rate

        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_a_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p) - r
        plant.ore2_stock.rate = r * p

        plant.ore1_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        # NOTE: Cross-stockout physical preemption added here.
        # If Ore 2 runs out while surging, the plant drops into ModeAContingency.
        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeAContingency()

        if plant.ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_a_ore1_milling_rate * 1.0 / (1.0 - p)

        plant.ore_extraction.rate = r
        r_mill = c.mode_a_ore1_milling_rate + c.mode_a_ore2_milling_rate
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r_mill * getattr(c, "mode_a_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r_mill
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = (
            r - c.mode_a_ore1_milling_rate - c.mode_a_ore2_milling_rate
        )
        plant.ore1_stock.rate = 0.0
        plant.ore2_stock.rate = r * p - c.mode_a_ore2_milling_rate

        plant.ore_stock.lower_threshold = c.target_ore_stock_level
        plant.ore2_stock.lower_threshold = 0.0


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
        return plant.ore2_stock.value < plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeBContingency()

        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeBMineSurging()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate

        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_b_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p) - c.mode_b_ore1_milling_rate
        plant.ore2_stock.rate = r * p - c.mode_b_ore2_milling_rate

        plant.ore1_stock.lower_threshold = 0.0
        plant.ore2_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeBMineSurging()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_b_contingency_ore2_milling_rate

        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_b_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p)
        plant.ore2_stock.rate = r * p - r

        plant.ore2_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        # NOTE: Cross-stockout physical preemption added here.
        # If Ore 1 runs out while surging, the plant drops into ModeBContingency.
        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeBContingency()

        if plant.ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_b_ore2_milling_rate * 1.0 / p

        plant.ore_extraction.rate = r
        r_mill = c.mode_b_ore1_milling_rate + c.mode_b_ore2_milling_rate
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r_mill * getattr(c, "mode_b_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r_mill
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = (
            r - c.mode_b_ore1_milling_rate - c.mode_b_ore2_milling_rate
        )
        plant.ore1_stock.rate = r * (1.0 - p) - c.mode_b_ore1_milling_rate
        plant.ore2_stock.rate = 0.0

        plant.ore_stock.lower_threshold = c.target_ore_stock_level
        plant.ore1_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        controller = model.controller
        if controller.is_campaign_complete():
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        controller = model.controller
        controller.time_shutdown.rate = 1.0
        if hasattr(model.plant, "total_cyanide_consumed"):
            model.plant.total_cyanide_consumed.rate = 0.0
        if hasattr(model.plant, "total_ore_milled"):
            model.plant.total_ore_milled.rate = 0.0
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
        return plant.ore2_stock.value >= plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeCMineSurging()

        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeCContingency()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_c_ore1_milling_rate + c.mode_c_ore2_milling_rate

        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_c_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p) - c.mode_c_ore1_milling_rate
        plant.ore2_stock.rate = r * p - c.mode_c_ore2_milling_rate

        plant.ore1_stock.lower_threshold = 0.0
        plant.ore2_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            return ModeCMineSurging()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_c_contingency_ore1_milling_rate

        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_c_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p) - r
        plant.ore2_stock.rate = r * p

        plant.ore1_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeCContingency()

        if plant.ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_c_ore1_milling_rate * 1.0 / (1.0 - p)

        plant.ore_extraction.rate = r
        r_mill = c.mode_c_ore1_milling_rate + c.mode_c_ore2_milling_rate
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r_mill * getattr(c, "mode_c_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r_mill
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = (
            r - c.mode_c_ore1_milling_rate - c.mode_c_ore2_milling_rate
        )
        plant.ore1_stock.rate = 0.0
        plant.ore2_stock.rate = r * p - c.mode_c_ore2_milling_rate

        plant.ore_stock.lower_threshold = c.target_ore_stock_level
        plant.ore2_stock.lower_threshold = 0.0


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
        return plant.ore2_stock.value < plant.config.critical_ore2_level

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeDContingency()

        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeDMineSurging()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_d_ore1_milling_rate + c.mode_d_ore2_milling_rate

        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_d_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p) - c.mode_d_ore1_milling_rate
        plant.ore2_stock.rate = r * p - c.mode_d_ore2_milling_rate

        plant.ore1_stock.lower_threshold = 0.0
        plant.ore2_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if controller.is_contingency_complete():
            return RequireDecision()

        if plant.ore2_stock.value <= plant.config.stockout_epsilon:
            return ModeDMineSurging()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_d_contingency_ore2_milling_rate

        plant.ore_extraction.rate = r
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r * getattr(c, "mode_d_contingency_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = 0.0
        plant.ore1_stock.rate = r * (1.0 - p)
        plant.ore2_stock.rate = r * p - r

        plant.ore2_stock.lower_threshold = 0.0


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
        return True

    def check_end_conditions(self, model: drs.Module):
        plant = model.plant
        controller = model.controller

        if controller.is_campaign_complete():
            return RequireDecision()

        if plant.ore1_stock.value <= plant.config.stockout_epsilon:
            controller.reset_contingency_timer()
            return ModeDContingency()

        if plant.ore_stock.value <= plant.config.target_ore_stock_level:
            return RequireDecision()

        return None

    def apply_dynamics(self, model: drs.Module):
        plant = model.plant
        controller = model.controller
        c = plant.config

        p = plant.current_parcel_routing_fraction
        r = c.mode_d_ore2_milling_rate * 1.0 / p

        plant.ore_extraction.rate = r
        r_mill = c.mode_d_ore1_milling_rate + c.mode_d_ore2_milling_rate
        if hasattr(plant, "total_cyanide_consumed"):
            plant.total_cyanide_consumed.rate = r_mill * getattr(c, "mode_d_avg_cyanide", 0.0)
        if hasattr(plant, "total_ore_milled"):
            plant.total_ore_milled.rate = r_mill
        plant.ore_extracted_from_current_parcel.rate = r
        plant.ore_stock.rate = (
            r - c.mode_d_ore1_milling_rate - c.mode_d_ore2_milling_rate
        )
        plant.ore1_stock.rate = r * (1.0 - p) - c.mode_d_ore1_milling_rate
        plant.ore2_stock.rate = 0.0

        plant.ore_stock.lower_threshold = c.target_ore_stock_level
        plant.ore1_stock.lower_threshold = 0.0


        controller.time_mode_d_surging.rate = 1.0
        controller.time_executed_campaign_shutdown.rate = 1.0
        controller.time_executed_campaign_shutdown.upper_threshold = (
            controller.config.duration_of_production_campaigns
        )
