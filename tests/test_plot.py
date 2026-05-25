import pytest
from mining_drs.plot import plot_time_series


def test_plot_time_series_missing_time_column():
    import pandas as pd

    # Missing 'time' column
    df = pd.DataFrame({"ore_stock": [100, 200, 300]})

    with pytest.raises(ValueError, match="DataFrame must contain a 'time' column"):
        plot_time_series(df, y_columns=["ore_stock"])


def test_plot_time_series_success():
    import pandas as pd

    df = pd.DataFrame(
        {
            "time": [0.0, 1.0, 2.0],
            "ore_stock": [100.0, 150.0, 120.0],
            "fuel_level": [500.0, 480.0, 460.0],
        }
    )

    fig = plot_time_series(df, y_columns=["ore_stock", "fuel_level"], title="Test Plot")

    # Verify a matplotlib figure was returned
    import matplotlib.figure

    assert isinstance(fig, matplotlib.figure.Figure)
    assert fig.axes[0].get_title() == "Test Plot"
