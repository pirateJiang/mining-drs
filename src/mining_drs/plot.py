try:
    import plotly.express as px

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def plot_time_series(
    df, y_columns: list, title: str = "Simulation Output", y_label: str = "Value"
):
    """
    Generates a line chart from a telemetry DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame from engine.telemetry.to_dataframe()
        y_columns (list): A list of column names (variables) to plot on the Y axis.
        title (str): The title of the plot.
        y_label (str): The label for the Y axis.

    Returns:
        plotly.graph_objs._figure.Figure: The plotly figure object. Call .show() to render.
    """
    if not PLOTLY_AVAILABLE:
        raise ImportError(
            "plotly is required to generate plots. Please install it via 'pip install plotly'."
        )

    if "time" not in df.columns:
        raise ValueError(
            "DataFrame must contain a 'time' column for time-series plotting."
        )

    fig = px.line(
        df,
        x="time",
        y=y_columns,
        title=title,
        labels={"value": y_label, "time": "Simulation Time", "variable": "Metrics"},
    )

    # Enhance the aesthetics natively
    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig
