import pytest
import numpy as np
import random


@pytest.fixture(autouse=True)
def seed_everything():
    """Seed all standard random number generators for reproducibility."""
    seed = 42
    random.seed(seed)
    np.random.seed(seed)
