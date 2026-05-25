import matplotlib.pyplot as plt


def plot_time_series(
    df, y_columns: list, title: str = "Simulation Output", y_label: str = "Value"
):
    """
    Generates a line chart from a telemetry DataFrame using Matplotlib.

    Args:
        df (pd.DataFrame): The DataFrame from engine.telemetry.to_dataframe()
        y_columns (list): A list of column names (variables) to plot on the Y axis.
        title (str): The title of the plot.
        y_label (str): The label for the Y axis.

    Returns:
        matplotlib.figure.Figure: The matplotlib figure object. Call plt.show() or fig.show() to render.
    """
    if "time" not in df.columns:
        raise ValueError(
            "DataFrame must contain a 'time' column for time-series plotting."
        )

    # Use a nice default style
    plt.style.use('seaborn-v0_8-whitegrid')
    
    fig, ax = plt.subplots(figsize=(10, 6))

    for col in y_columns:
        if col in df.columns:
            ax.plot(df["time"], df[col], label=col, linewidth=2)

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("Simulation Time", fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    
    # Legend settings
    ax.legend(loc='upper right', bbox_to_anchor=(1, 1.1), ncol=len(y_columns), frameon=True)
    
    fig.tight_layout()

    return fig
