from abc import ABC, abstractmethod

class DRSEngine(ABC):
    """
    Base class for DRS simulation engines.
    Abstracts the Arena '5 Islands' into a synchronized execution loop.
    """
    
    def run(self):
        """The main simulation loop executing the 5 islands sequentially."""
        self.initialize_state() # Island 1
        
        while not self.is_terminating_condition_met():
            dt = self.calculate_time_to_next_threshold() # Island 2
            
            # Prevent infinite loops if dt is 0 but conditions aren't advancing
            if dt < 0:
                raise ValueError("Time delta (dt) cannot be negative.")
                
            self.advance_time(dt)                        # Island 3
            self.check_and_trigger_thresholds()          # Island 4
            self.record_statistics()                     # Island 5

    @abstractmethod
    def initialize_state(self):
        """Island 1: Set up initial variables, levels, timers, and trackers."""
        pass

    @abstractmethod
    def is_terminating_condition_met(self) -> bool:
        """Check if the simulation should stop (e.g., max time reached)."""
        pass

    @abstractmethod
    def calculate_time_to_next_threshold(self) -> float:
        """Island 2: Determine the time step (dt) to the next event/threshold."""
        pass

    @abstractmethod
    def advance_time(self, dt: float):
        """Island 3: Update levels and internal clocks by dt."""
        pass

    @abstractmethod
    def check_and_trigger_thresholds(self):
        """Island 4: Evaluate condition changes and execute triggered logic."""
        pass

    @abstractmethod
    def record_statistics(self):
        """Island 5: Log metrics for output reporting."""
        pass
