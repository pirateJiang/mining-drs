import random

class OreBodyModel:
    """
    Represents the spatial distribution of ore grades in the earth.
    Decouples geostatistical modeling from the simulation loop.
    """
    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.block_model = self._generate_spatial_model(parameters)
        self.current_index = 0
        self.total_parcels = len(self.block_model)

    def _generate_spatial_model(self, parameters: dict) -> list:
        """
        Pre-generates a block model representing spatially correlated parcels.
        In a production environment, this would use Kriging or SGS via libraries 
        like GeostatsPy or scikit-gstat.
        
        For this abstraction, we generate a basic 1D spatially correlated 
        array using a moving average smoothing over random gaussian noise.
        """
        num_parcels = parameters.get('num_parcels', 1000)
        mean_grade = parameters.get('mean_grade', 5.0)
        std_dev = parameters.get('std_dev', 1.0)
        
        # 1. Generate independent random gaussian noise
        raw_noise = [random.gauss(mean_grade, std_dev) for _ in range(num_parcels)]
        
        # 2. Apply a basic moving average to simulate spatial correlation
        window_size = parameters.get('correlation_window', 5)
        correlated_model = []
        
        for i in range(num_parcels):
            # Get a slice of the window surrounding the current parcel
            start = max(0, i - window_size // 2)
            end = min(num_parcels, i + window_size // 2 + 1)
            window_slice = raw_noise[start:end]
            
            # The parcel grade is the average of its neighbors
            smoothed_grade = sum(window_slice) / len(window_slice)
            correlated_model.append(max(0.0, smoothed_grade)) # Ore grade can't be negative
            
        return correlated_model

    def get_next_parcel(self) -> float:
        """
        Retrieves the next physical parcel of ore from the sequence.
        """
        if self.current_index >= self.total_parcels:
            raise IndexError("No more parcels available in the block model.")
            
        parcel = self.block_model[self.current_index]
        self.current_index += 1
        return parcel
    
    def has_more_parcels(self) -> bool:
        """Returns True if there are more parcels to extract."""
        return self.current_index < self.total_parcels
