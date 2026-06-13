from typing import Tuple
import math
from drs.module import drs
from drs.flow import Flow
from .data import MineOutput



class DiscreteFleetLogistics(drs.Module):
    def __init__(self):
        super().__init__()
        self.name = "Fleet"
        self.transit_queue = []
        # Timer forces engine to stop exactly when a truck arrives
        self.time_to_next_arrival = drs.Timer(
            "time_to_next_arrival", math.inf, rate=-1.0
        )
        self.time_to_next_arrival.lower_threshold = 0.0

    def forward(self, *incoming_flows):
        current_time = self.parent.global_time.value

        for flow in incoming_flows:
            if flow is not None:
                travel_time, parcel = flow.value
                arrival = current_time + travel_time
                self.transit_queue.append((arrival, parcel))

        self.transit_queue.sort(key=lambda x: x[0])

        if self.transit_queue:
            self.time_to_next_arrival.value = self.transit_queue[0][0] - current_time
        else:
            self.time_to_next_arrival.value = math.inf

        if self.time_to_next_arrival.value <= 1e-6 and self.transit_queue:
            _, parcel = self.transit_queue.pop(0)

            # True routing policy: Ore 1 to Stock 1, Ore 2 to Stock 2
            self.parent.ore1_stock.current_mass.value += parcel.ore1
            self.parent.ore2_stock.current_mass.value += parcel.ore2

            if self.transit_queue:
                self.time_to_next_arrival.value = (
                    self.transit_queue[0][0] - current_time
                )
            else:
                self.time_to_next_arrival.value = math.inf


class ContinuousFleetLogistics(drs.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.stockpile2_routing_fraction = drs.Variable(
            "stockpile2_routing_fraction", 0.0
        )

    def forward(self, *mine_flows):
        total_ore1_rate = 0.0
        total_ore2_rate = 0.0
        total_rate = 0.0
        for flow in mine_flows:
            if flow is not None:
                out = flow.value
                ore1_frac = out.attr_value
                total_ore1_rate += out.extraction_rate * ore1_frac
                total_ore2_rate += out.extraction_rate * (1.0 - ore1_frac)
                total_rate += out.extraction_rate

        if total_rate > 1e-6:
            self.stockpile2_routing_fraction.value = total_ore2_rate / total_rate
        else:
            self.stockpile2_routing_fraction.value = 0.0

        # Output pure Ore 1 rate and pure Ore 2 rate
        return Flow(value=MineOutput(total_ore1_rate, 0, 1.0)), Flow(
            value=MineOutput(total_ore2_rate, 0, 0.0)
        )


