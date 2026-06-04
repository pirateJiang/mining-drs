import pytest
from drs.module import Module
from drs.variables import Level, Timer

def test_module_variable_list_registration():
    class TestModule(Module):
        def __init__(self):
            super().__init__()
            self.trucks = [Level(f"truck_{i}", 0.0) for i in range(5)]
            self.single = Timer("single_timer", 0.0)
            
        def update_rates(self):
            pass

    mod = TestModule()
    
    # 5 trucks + 1 single = 6 variables
    vars_list = list(mod.variables())
    assert len(vars_list) == 6
    
    # Check that they were registered with the expected names
    # They should be accessible in mod._variables with name_{i}
    assert "trucks_0" in mod._variables
    assert "trucks_4" in mod._variables
    assert "single" in mod._variables

    assert mod._variables["trucks_0"].name == "truck_0"
    assert mod._variables["trucks_4"].name == "truck_4"
