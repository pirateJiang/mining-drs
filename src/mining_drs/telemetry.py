try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

class Telemetry:
    """
    Automates the recording of all simulation variables over time.
    Provides methods to export the recorded history into analysis-ready formats.
    """
    def __init__(self, engine):
        """
        Initializes the telemetry system attached to a specific engine.
        The engine is expected to have a `variables` attribute (a list of Variable objects).
        """
        self.engine = engine
        self.history = []

    def snapshot(self, current_time: float):
        """
        Called automatically at the end of every simulation tick to record the state.
        """
        state = {'time': current_time}
        
        # Dynamically grab the value of every tracked variable
        if hasattr(self.engine, 'variables'):
            for variable in self.engine.variables:
                state[variable.name] = variable.value
                
        self.history.append(state)

    def to_dataframe(self):
        """
        Converts the entire simulation history into a Pandas DataFrame for plotting/analysis.
        Raises an ImportError if pandas is not installed.
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required to export telemetry to a DataFrame. Please install it via 'pip install pandas'.")
        
        return pd.DataFrame(self.history)
    
    def get_raw_history(self) -> list:
        """
        Returns the raw list of dictionary states.
        """
        return self.history
