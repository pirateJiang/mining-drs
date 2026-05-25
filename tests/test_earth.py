import pytest
from mining_drs.earth import OreBodyModel

def test_ore_body_model_initialization():
    params = {
        'num_parcels': 50,
        'mean_grade': 2.5,
        'std_dev': 0.5,
        'correlation_window': 3
    }
    model = OreBodyModel(params)
    
    # Check that 50 parcels were pre-generated
    assert model.total_parcels == 50
    assert len(model.block_model) == 50
    assert model.current_index == 0

def test_ore_body_model_get_next_parcel():
    params = {'num_parcels': 5}
    model = OreBodyModel(params)
    
    for i in range(5):
        assert model.has_more_parcels() is True
        parcel = model.get_next_parcel()
        assert isinstance(parcel, float)
        assert parcel >= 0.0 # Grade shouldn't be negative
        assert model.current_index == i + 1
        
    assert model.has_more_parcels() is False
    
    with pytest.raises(IndexError, match="No more parcels available"):
        model.get_next_parcel()

def test_ore_body_model_spatial_correlation_effect():
    # We test that a large window causes smoothing (less variance than raw noise)
    params = {
        'num_parcels': 1000,
        'mean_grade': 5.0,
        'std_dev': 2.0,
        'correlation_window': 50 # Large window for heavy smoothing
    }
    model = OreBodyModel(params)
    
    # Calculate empirical variance of the smoothed model
    mean_val = sum(model.block_model) / len(model.block_model)
    variance = sum((x - mean_val) ** 2 for x in model.block_model) / len(model.block_model)
    
    # With a window of 50, the variance should be significantly lower than the input variance (2.0^2 = 4.0)
    assert variance < 1.0
