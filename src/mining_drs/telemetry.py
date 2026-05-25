import pandas as pd


class Telemetry:
    """
    Automates the recording of all simulation variables over time.
    Provides methods to export the recorded history into analysis-ready formats.
    """

    def __init__(self, model):
        """
        Initializes the telemetry system attached to a specific model.
        The model is expected to provide a `variables()` method (an iterator of Variable objects).
        """
        self.model = model
        self.history = []

    def snapshot(self, current_time: float):
        """
        Called automatically at the end of every simulation tick to record the state.
        """
        state = {"time": current_time}

        for variable in self.model.variables():
            state[variable.name] = variable.value

        self.history.append(state)

    def to_dataframe(self):
        """
        Converts the entire simulation history into a Pandas DataFrame for plotting/analysis.
        """
        return pd.DataFrame(self.history)

    def get_raw_history(self) -> list:
        """
        Returns the raw list of dictionary states.
        """
        return self.history

    # TODO: do we still need this?
    def record_custom(self, key: str, value: any):
        """
        Records a custom key-value pair to the most recent snapshot in the history.
        Raises an error if no snapshot has been taken yet.
        """
        if not self.history:
            raise IndexError(
                "Cannot record custom data: No snapshots have been taken yet."
            )
        self.history[-1][key] = value
