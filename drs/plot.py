import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

# TODO: make them all use seaborn for plotting?
import seaborn as sns


# TODO: clean this up so its easier and a nicer api to combine plots into one image and we dont need to use the complete diagnostics function.
# TODO: this is very general. should we make it more specific? should we use this as a helper internally in other plots?
def plot_time_series(
    df,
    y_columns: list,
    time_col: str = "time",
    title: str = None,
    y_label: str = None,
    is_step: bool = False,
    ax=None,
    add_legend: bool = True,
    colors: list = None,
    **line_kwargs,
):
    """
    Generates a line chart from a telemetry DataFrame using Matplotlib.
    Can be used as a standalone plot or as an internal base for other plot functions.

    Args:
        df (pd.DataFrame): The DataFrame from engine.telemetry.to_dataframe()
        y_columns (list): A list of column names (variables) to plot on the Y axis.
        time_col (str): The column name for the time axis.
        title (str, optional): The title of the plot.
        y_label (str, optional): The label for the Y axis.
        is_step (bool): If True, plots as a step function.
        ax (matplotlib.axes.Axes, optional): An existing axes to plot on.
        add_legend (bool): Whether to automatically add a legend.
        colors (list, optional): List of colors to cycle through for the lines.
        **line_kwargs: Additional arguments passed to ax.plot or ax.step (e.g. alpha, zorder, linewidth).

    Returns:
        matplotlib.figure.Figure or matplotlib.axes.Axes: The figure object if ax is None, otherwise the ax.
    """
    if time_col not in df.columns:
        raise ValueError(
            f"DataFrame must contain a '{time_col}' column for time-series plotting."
        )

    # Use a nice default style
    plt.style.use("seaborn-v0_8-whitegrid")

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    for i, col in enumerate(y_columns):
        if col in df.columns:
            color = colors[i % len(colors)] if colors else None

            kwargs = dict(line_kwargs)
            kwargs.setdefault("linewidth", 2)

            if is_step:
                kwargs.setdefault("where", "post")
                ax.step(df[time_col], df[col], label=col, color=color, **kwargs)
            else:
                ax.plot(df[time_col], df[col], label=col, color=color, **kwargs)

    if title:
        ax.set_title(title, fontsize=14, pad=15)
    if y_label:
        ax.set_ylabel(y_label, fontsize=12)

    if add_legend:
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1, 1.1),
            ncol=len(y_columns),
            frameon=True,
        )

    if own_ax:
        fig = ax.figure
        fig.tight_layout()
        return fig
    return ax


def plot_ore_with_modes(
    df,
    time_col="time",
    ore_cols=None,
    mode_col="current_mode",
    title="Ore Stockpiles with Mode Switch Markers",
    campaign_split_mode=None,
    hlines=None,
    ax=None,
    palette=None,
):
    """
    Plots one or more ore stockpile time series with color-coded mode regions
    and vertical dashed lines marking mode switches.

    Each unique mode gets a distinct background color (via axvspan) so you can
    see at a glance which mode was active during each time interval. Vertical
    dashed lines mark the exact transition points.

    If campaign_split_mode is provided (e.g., MineMode.SHUTDOWN), that mode will
    be shaded with a subtle grey. The start of each active campaign (exiting shutdown)
    will be marked with an 'X' on the primary ore line to denote the decision point.

    Args:
        df (pd.DataFrame): The DataFrame from engine.telemetry.to_dataframe().
        time_col (str): Column name for the time axis.
        ore_cols (list or str, optional): Column name(s) for the ore stockpile
            level(s). Pass a single string or a list of strings. If None,
            defaults to ["ore_stock"].
        mode_col (str): Column name for the current operating mode.
        title (str): Plot title.
        campaign_split_mode (any, optional): The mode value that demarcates
            campaigns (usually the Shutdown mode).
        ax (matplotlib.axes.Axes, optional): An existing axes to plot on.

    Returns:
        matplotlib.figure.Figure or matplotlib.axes.Axes: The figure object if ax is None, otherwise the ax.
    """
    # Normalise ore_cols to a list
    if ore_cols is None:
        ore_cols = ["ore_stock"]
    elif isinstance(ore_cols, str):
        ore_cols = [ore_cols]

    if ax is None:
        fig, ax = plt.subplots(figsize=(14, 7))
        own_ax = True
    else:
        own_ax = False

    # --- Build a colour map for each unique mode ---
    unique_modes = df[mode_col].unique()
    import matplotlib

    cmap = matplotlib.colormaps["tab10"]
    palette = palette or {}

    mode_colors = {}
    for i, mode in enumerate(unique_modes):
        mode_name = getattr(mode, "name", str(mode))
        mode_str = str(mode).split('.')[-1].upper() # Fallback for enum string representation
        
        if mode_name in palette:
            mode_colors[mode] = palette[mode_name]
        elif mode_str in palette:
            mode_colors[mode] = palette[mode_str]
        else:
            mode_colors[mode] = cmap(i % 10)

    # Override shutdown color to a bright gold if provided (just in case it wasn't caught above)
    if campaign_split_mode is not None and campaign_split_mode in unique_modes:
        mode_colors[campaign_split_mode] = "#FFD700"

    # --- Shade background by active mode (axvspan) ---
    # Find the indices where mode changes (including the very first row)
    change_idx = df.index[df[mode_col] != df[mode_col].shift(1)].tolist()

    for i, start_idx in enumerate(change_idx):
        mode = df.loc[start_idx, mode_col]
        t_start = df.loc[start_idx, time_col]

        # End of this region is the start of the next, or end of data
        if i + 1 < len(change_idx):
            t_end = df.loc[change_idx[i + 1], time_col]
        else:
            t_end = df[time_col].iloc[-1]

        alpha_val = (
            0.75
            if (campaign_split_mode is not None and mode == campaign_split_mode)
            else 0.10
        )
        ax.axvspan(t_start, t_end, alpha=alpha_val, color=mode_colors[mode])

    # --- Plot the ore stockpile lines using our base helper ---
    ore_line_colors = ["black", "#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b"]
    plot_time_series(
        df,
        y_columns=ore_cols,
        time_col=time_col,
        ax=ax,
        add_legend=False,
        colors=ore_line_colors,
        alpha=0.9,
        zorder=3,
    )

    # --- Add vertical dashed lines at each mode switch ---
    for start_idx in change_idx:
        if start_idx == df.index[0]:
            continue  # skip the initial state

        mode = df.loc[start_idx, mode_col]
        t = df.loc[start_idx, time_col]
        color = mode_colors[mode]

        ax.axvline(x=t, color=color, linestyle="--", linewidth=1.2, alpha=0.7, zorder=2)

    # --- Add Campaign 'X' Markers ---
    if campaign_split_mode is not None:
        campaign_starts = []
        in_campaign = False

        for start_idx in change_idx:
            mode = df.loc[start_idx, mode_col]
            t_start = df.loc[start_idx, time_col]

            if mode != campaign_split_mode and not in_campaign:
                in_campaign = True
                campaign_starts.append((t_start, start_idx))
            elif mode == campaign_split_mode and in_campaign:
                in_campaign = False

        primary_ore = (
            ore_cols[0] if len(ore_cols) > 0 and ore_cols[0] in df.columns else None
        )

        for i, (t_start, idx) in enumerate(campaign_starts):
            if primary_ore:
                y_val = df.loc[idx, primary_ore]
                # Plot an 'X' marker on the line
                ax.plot(
                    t_start, y_val, marker="X", color="black", markersize=9, zorder=5
                )
                # Label it right above the marker
                ax.text(
                    t_start,
                    y_val + (ax.get_ylim()[1] * 0.03),
                    f"C{i+1}",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                    fontweight="bold",
                    color="black",
                    zorder=6,
                )

    # --- Add Reference Horizontal Lines ---
    if hlines:
        for hline in hlines:
            ax.axhline(**hline)

    # --- Build a combined legend (ore lines + mode colours) ---
    from matplotlib.patches import Patch

    mode_patches = [
        Patch(
            facecolor=mode_colors[m],
            alpha=0.75 if m == campaign_split_mode else 0.35,
            label=str(m),
        )
        for m in unique_modes
    ]
    ore_handles = ax.get_legend_handles_labels()[0]
    ore_labels = ax.get_legend_handles_labels()[1]

    # Combine: ore lines first, then mode patches
    all_handles = list(ore_handles) + mode_patches
    all_labels = list(ore_labels) + [str(m) for m in unique_modes]
    ax.legend(
        all_handles,
        all_labels,
        loc="upper right",
        bbox_to_anchor=(1, 1.12),
        ncol=min(len(all_labels), 5),
        frameon=True,
        fontsize=9,
    )
    ax.set_ylabel("Ore Stockpile", fontsize=12)
    ax.set_xlabel("Simulation Time", fontsize=12)
    ax.set_title(title, fontsize=14, pad=15)

    if own_ax:
        fig = ax.figure
        fig.tight_layout()
        return fig
    return ax


def plot_chattering(
    df,
    action_cols: list,
    state_col: str = None,
    time_col: str = "time",
    title: str = "Action Chattering Diagnostic",
):
    """
    Step-plots one or more action outputs over time, optionally overlaying
    the actual continuous state they are controlling.

    Use this to diagnose bang-bang control — an RL agent that oscillates
    between extreme values (100% -> 0% -> 100%) rather than learning smooth
    transitions. If the action traces look like square waves you likely need
    an action-difference penalty in your reward.

    Args:
        df (pd.DataFrame): Telemetry DataFrame.
        action_cols (list): Column names for the action outputs to plot as step functions.
        state_col (str, optional): Column name for the actual state to overlay as a
            smooth line. Pass None to skip.
        time_col (str): Column name for the time axis.
        title (str): Plot title.

    Returns:
        matplotlib.figure.Figure: The matplotlib figure object.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot the actual state as a smooth background line
    if state_col and state_col in df.columns:
        ax.plot(
            df[time_col],
            df[state_col],
            label=f"{state_col} (actual)",
            color="black",
            linewidth=2,
            alpha=0.6,
        )

    # Overlay action outputs as step functions
    colors = plt.cm.Set1.colors
    for i, col in enumerate(action_cols):
        if col in df.columns:
            color = colors[i % len(colors)]
            ax.step(
                df[time_col],
                df[col],
                label=f"{col} (action)",
                linewidth=1.5,
                where="post",
                color=color,
                alpha=0.85,
            )

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("Time", fontsize=12)
    ax.set_ylabel("Value", fontsize=12)
    ax.legend(loc="best", frameon=True)
    fig.tight_layout()
    return fig


def plot_safety_margin(
    df,
    level_col: str,
    constraint_value: float,
    time_col: str = "time",
    constraint_type: str = "upper",
    title: str = "Safety Margin (Distance to Constraint)",
    danger_threshold: float = None,
    ax=None,
):
    """
    Plots the distance between a state variable and its constraint over time.

    For an upper constraint (capacity): margin = constraint_value - level.
    For a lower constraint (floor):     margin = level - constraint_value.

    A margin of 0 means the constraint is active; negative means violated.
    This shows how "risky" the agent is — a good agent will ride just above 0
    without crossing it.

    Args:
        df (pd.DataFrame): Telemetry DataFrame.
        level_col (str): Column name for the current level / state variable.
        constraint_value (float): The constraint limit (e.g. max capacity or min floor).
        time_col (str): Column name for the time axis.
        constraint_type (str): 'upper' if the constraint is a ceiling (capacity),
            'lower' if it is a floor (minimum level).
        title (str): Plot title.
        danger_threshold (float, optional): If provided, fills the area below this
            margin value in red to highlight the danger zone.
        ax (matplotlib.axes.Axes, optional): An existing axes to plot on.

    Returns:
        matplotlib.figure.Figure or matplotlib.axes.Axes: The figure object if ax is None, otherwise the ax.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 6))
        own_ax = True
    else:
        own_ax = False

    if constraint_type == "upper":
        margin = constraint_value - df[level_col]
    else:
        margin = df[level_col] - constraint_value

    ax.plot(df[time_col], margin, label="Safety Margin", color="steelblue", linewidth=2)
    ax.axhline(
        y=0,
        color="red",
        linestyle="-",
        linewidth=1.5,
        alpha=0.8,
        label="Constraint Boundary",
    )

    # Shade the danger zone
    if danger_threshold is not None:
        ax.axhline(
            y=danger_threshold,
            color="orange",
            linestyle="--",
            linewidth=1,
            alpha=0.7,
            label=f"Danger Threshold ({danger_threshold})",
        )
        ax.fill_between(
            df[time_col],
            margin,
            0,
            where=(margin < danger_threshold),
            color="red",
            alpha=0.15,
            label="Danger Zone",
        )

    # Shade any actual violations
    ax.fill_between(
        df[time_col],
        margin,
        0,
        where=(margin < 0),
        color="red",
        alpha=0.3,
        label="Constraint Violated",
    )

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("Simulation Time", fontsize=12)
    ax.set_ylabel("Margin (distance to constraint)", fontsize=12)
    ax.legend(loc="best", frameon=True)

    if own_ax:
        fig = ax.figure
        fig.tight_layout()
        return fig
    return ax


def plot_dual_axis_step(
    df,
    y1_col: str,
    y2_col: str,
    y1_label: str = "Axis 1",
    y2_label: str = "Axis 2",
    y1_color: str = "saddlebrown",
    y2_color: str = "darkorange",
    time_col: str = "time",
    title: str = "Dual Axis Step Plot",
    ax=None,
):
    """
    Plots two variables as step functions on dual Y-axes (twinx).
    Useful for tracking variables with different scales/units simultaneously.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    if y1_col in df.columns:
        line1 = ax.step(
            df[time_col],
            df[y1_col],
            label=y1_label,
            color=y1_color,
            where="post",
            linewidth=2,
        )
        ax.set_ylabel(y1_label, color=y1_color, fontsize=12)
        ax.tick_params(axis="y", labelcolor=y1_color)
    else:
        line1 = []

    if y2_col in df.columns:
        ax_twin = ax.twinx()
        line2 = ax_twin.step(
            df[time_col],
            df[y2_col],
            label=y2_label,
            color=y2_color,
            where="post",
            linewidth=2,
        )
        ax_twin.set_ylabel(y2_label, color=y2_color, fontsize=12)
        ax_twin.tick_params(axis="y", labelcolor=y2_color)
    else:
        line2 = []

    lines = line1 + line2
    if lines:
        labels = [l.get_label() for l in lines]
        ax.legend(lines, labels, loc="upper right", bbox_to_anchor=(1.12, 1))

    ax.set_title(title, fontsize=14, pad=15)
    ax.grid(True)
    ax.set_xlabel("Simulation Time", fontsize=12)

    if own_ax:
        fig = ax.figure
        fig.tight_layout()
        return fig
    return ax


def build_dashboard(df, plot_configs, title="Simulation Dashboard", figsize=(16, 20)):
    """
    Dynamically builds a dashboard from a list of plot configurations.

    Args:
        df (pd.DataFrame): Telemetry DataFrame.
        plot_configs (list of dict): List specifying the function and kwargs for each subplot.
        title (str): Dashboard title.

    Example usage:
        configs = [
            {"func": plot_time_series, "kwargs": {"y_columns": ["Mode A", "Mode B"]}},
            {"func": plot_safety_margin, "kwargs": {"level_col": "Ore1Stock_Level", "constraint_value": 0}}
        ]
        fig = build_dashboard(df, configs)
    """
    num_plots = len(plot_configs)
    fig = plt.figure(figsize=figsize)
    gs = gridspec.GridSpec(num_plots, 1, figure=fig)

    axes = []
    time_ax = None
    for i, config in enumerate(plot_configs):
        func = config["func"]
        is_time_series = func.__name__ not in [
            "plot_state_space",
            "plot_mode_distribution",
            "plot_mode_dwell_times",
            "plot_normalized_deviation_violin",
            "plot_deficit_disparity",
            "plot_geology_impact",
            "plot_deficit_breakdown_pie",
            "plot_deficit_breakdown_bar",
            "plot_structural_vs_operational_by_mode",
        ]

        # Share the X-axis selectively for time-series plots to prevent cut-offs and misalignment
        if is_time_series:
            ax = fig.add_subplot(gs[i, 0], sharex=time_ax)
            if time_ax is None:
                time_ax = ax
        else:
            ax = fig.add_subplot(gs[i, 0])

        axes.append(ax)

        # Extract the function and its specific arguments
        func = config["func"]
        kwargs = config.get("kwargs", {})

        # Execute the plot function directly onto this specific axis
        func(df, ax=ax, **kwargs)

        # Explicitly ensure the x-label is shown
        ax.tick_params(labelbottom=True)

    fig.suptitle(title, fontsize=18, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def plot_state_space(
    df,
    col_x="TrueOre1Stock_mass",
    col_y="TrueOre2Stock_mass",
    title="State Space Trajectory",
    ax=None,
):
    """
    Plots the state-space (phase) portrait of two variables.
    Shows the trajectory of the plant's stockpiles over time.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))
        own_ax = True
    else:
        own_ax = False

    if col_x not in df.columns or col_y not in df.columns:
        if own_ax:
            return fig
        return ax

    # Plot the trajectory
    ax.plot(df[col_x], df[col_y], color="gray", alpha=0.5, linewidth=1, zorder=1)

    # Scatter points color-coded by time to show directionality
    time_col = "time" if "time" in df.columns else df.columns[0]
    scatter = ax.scatter(
        df[col_x], df[col_y], c=df[time_col], cmap="viridis", s=10, zorder=2
    )

    if own_ax:
        plt.colorbar(scatter, ax=ax, label="Simulation Time")

    # Mark the start and end points
    ax.plot(
        df[col_x].iloc[0],
        df[col_y].iloc[0],
        "go",
        markersize=10,
        label="Start",
        zorder=3,
    )
    ax.plot(
        df[col_x].iloc[-1],
        df[col_y].iloc[-1],
        "ro",
        markersize=10,
        label="End",
        zorder=3,
    )

    ax.set_xlabel(col_x, fontsize=12)
    ax.set_ylabel(col_y, fontsize=12)
    ax.set_title(title, fontsize=14, pad=15)
    ax.axhline(0, color="red", linestyle="--", alpha=0.5)  # Floor constraint
    ax.axvline(0, color="red", linestyle="--", alpha=0.5)  # Floor constraint
    ax.legend(loc="upper left")
    ax.grid(True)

    if own_ax:
        fig.tight_layout()
        return fig
    return ax


def plot_mode_distribution(
    df,
    mode_col="current_mode",
    time_col="time",
    title="Mode Distribution (% Time)",
    ax=None,
    palette=None,
    verbose=True,
):
    """
    Visualizes the percentage of time spent in each mode as a horizontal bar chart.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
        own_ax = True
    else:
        own_ax = False

    if mode_col not in df.columns or time_col not in df.columns:
        if own_ax:
            return fig
        return ax

    # Calculate exact duration for each active mode window
    df_sorted = df.copy()
    df_sorted["dt"] = df_sorted[time_col].diff().shift(-1).fillna(0)

    # Cast mode column to string to avoid Enum sorting errors in pandas groupby
    df_sorted["mode_str"] = df_sorted[mode_col].apply(
        lambda x: getattr(x, "name", str(x))
    )

    # Group by mode and sum
    durations = df_sorted.groupby("mode_str")["dt"].sum()
    total_time = durations.sum()

    if total_time > 0:
        percentages = (durations / total_time) * 100
    else:
        percentages = durations * 0

    percentages = percentages.sort_values(ascending=True)

    if verbose:
        print(f"\n--- {title} ---")
        for mode, pct in percentages.items():
            print(f"{mode}: {pct:.1f}%")
        print("-" * (8 + len(title)))

    # Try to use consistent colors
    import matplotlib

    cmap = matplotlib.colormaps["tab10"]
    palette = palette or {}

    colors = []
    for mode in percentages.index:
        mode_name = getattr(mode, "name", str(mode))
        mode_str = str(mode).split('.')[-1].upper()
        if mode_name in palette:
            colors.append(palette[mode_name])
        elif mode_str in palette:
            colors.append(palette[mode_str])
        else:
            idx = sum(ord(c) for c in str(mode)) % 10
            colors.append(cmap(idx))

    bars = ax.barh(
        percentages.index.astype(str), percentages.values, color=colors, alpha=0.8
    )

    # Add percentage labels to the right of each bar
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.1f}%",
            va="center",
            ha="left",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("% of Total Simulation Time", fontsize=12)
    ax.set_xlim(0, max(100, percentages.max() + 10))
    ax.grid(axis="x", linestyle="--", alpha=0.7)

    if own_ax:
        fig.tight_layout()
        return fig
    return ax


def plot_cumulative_throughput(
    df,
    extraction_col="TrueOreExtraction_Level",
    time_col="time",
    ideal_rate=None,
    title="Cumulative Throughput vs Target",
    ax=None,
):
    """
    Plots cumulative extraction over time, overlaid with an ideal target rate.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    if extraction_col not in df.columns or time_col not in df.columns:
        if own_ax:
            return fig
        return ax

    ax.plot(
        df[time_col],
        df[extraction_col],
        label="Actual Extraction",
        color="green",
        linewidth=2,
    )

    if ideal_rate is not None:
        min_time = df[time_col].min()
        max_time = df[time_col].max()
        ideal_times = [min_time, max_time]

        start_val = df[extraction_col].min()
        ideal_vals = [start_val, start_val + ideal_rate * (max_time - min_time)]

        ax.plot(
            ideal_times,
            ideal_vals,
            "k--",
            label=f"Ideal Rate ({ideal_rate}/t)",
            alpha=0.7,
            linewidth=2,
        )

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_ylabel("Cumulative Ore Extracted", fontsize=12)
    ax.legend(loc="upper left")
    ax.grid(True)

    if own_ax:
        fig.tight_layout()
        return fig
    return ax


def plot_mode_dwell_times(df, time_col="time", mode_col="current_mode", title="Mode Stability (Dwell Times)", ax=None, verbose=True):
    """
    Identifies how long the system stays in each mode before switching.
    Crucial for diagnosing 'chattering' (rapid switching) to optimize thresholds.
    """
    # Convert modes to strings to prevent pandas Enum sorting TypeErrors
    df = df.copy()
    df[mode_col] = df[mode_col].astype(str)

    # Group consecutive identical modes to calculate durations
    # This pandas trick creates a unique ID for each contiguous block of the same mode
    blocks = (df[mode_col] != df[mode_col].shift(1)).cumsum().rename("block")

    # Calculate exact duration for each active mode window by taking forward diff
    # so that the interval [time[i], time[i+1]] is correctly attributed to mode[i]
    df["dt"] = df[time_col].diff().shift(-1).fillna(0)
    
    # Calculate duration of each block
    durations = (
        df.groupby([blocks, mode_col])["dt"].sum()
        .reset_index()
    )
    durations.columns = ["block", "mode", "duration"]

    # Filter out 0-duration blocks (instantaneous transitions)
    durations = durations[durations["duration"] > 0.01]

    if verbose:
        print(f"\n--- {title} ---")
        dwell_summary = durations.groupby('mode')['duration'].agg(['count', 'mean', 'median', 'max'])
        print(dwell_summary.round(2).to_string())
        print("-" * (8 + len(title)))

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    # Use a boxplot to show the distribution of time spent in each mode
    sns.boxplot(data=durations, x="duration", y="mode", ax=ax, palette="Set2", hue="mode", legend=False)
    sns.stripplot(
        data=durations, x="duration", y="mode", color="black", alpha=0.4, size=4, ax=ax
    )

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("Duration Before Switch (Days)", fontsize=12)
    ax.set_ylabel("")

    # Add a red warning line for anything under 2 days (Chattering zone)
    ax.axvline(
        x=2.0,
        color="red",
        linestyle="--",
        alpha=0.5,
        label="Chattering Threshold (<2 days)",
    )
    ax.legend(loc="lower right")

    if own_ax:
        fig = ax.figure
        fig.tight_layout()
        return fig
    return ax


def plot_normalized_deviation_violin(
    df, 
    title="Stockpile Deviation Variance (Violin)", 
    target_total=60000.0,
    target_ore1=42000.0,
    target_ore2=18000.0,
    col_total="TrueOreStock_Level",
    col_ore1="TrueOre1Stock_mass",
    col_ore2="TrueOre2Stock_mass",
    ax=None
):
    """
    Uses a Violin Plot to show distributions side-by-side without Y-axis squashing.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    # 1. Calculate Deviations
    # Fallback to old names if new names aren't present
    if col_total not in df.columns and "OreStock_Level" in df.columns:
        col_total = "OreStock_Level"
    if col_ore1 not in df.columns and "Ore1Stock_Level" in df.columns:
        col_ore1 = "Ore1Stock_Level"
    if col_ore2 not in df.columns and "Ore2Stock_Level" in df.columns:
        col_ore2 = "Ore2Stock_Level"

    dev_total = ((df[col_total] - target_total) / target_total) * 100 if target_total else df[col_total] * 0
    dev_ore1 = ((df[col_ore1] - target_ore1) / target_ore1) * 100 if target_ore1 else df[col_ore1] * 0
    dev_ore2 = ((df[col_ore2] - target_ore2) / target_ore2) * 100 if target_ore2 else df[col_ore2] * 0

    # 2. Package into a new DataFrame and Melt it for Seaborn
    dev_df = pd.DataFrame({
        "Total Stockpile": dev_total,
        "Ore 1": dev_ore1,
        "Ore 2": dev_ore2
    })
    melted_df = dev_df.melt(var_name="Stockpile Type", value_name="Deviation (%)")

    # 3. Plot the Violins
    palette = {"Total Stockpile": "gray", "Ore 1": "#1f77b4", "Ore 2": "#d62728"}
    
    sns.violinplot(
        data=melted_df, 
        y="Stockpile Type", 
        x="Deviation (%)", 
        hue="Stockpile Type", # Adding hue and legend=False to suppress seaborn future warnings
        legend=False,
        palette=palette, 
        inner="quartile", # Draws lines for median and interquartile range inside the violin
        cut=0,            # Prevents the tails from extending past the actual data limits
        ax=ax
    )

    # 4. Add the Perfect Control Line
    ax.axvline(x=0, color='black', linestyle='--', linewidth=2, label="Perfect Target (0%)", zorder=0)

    # 5. Formatting
    ax.set_title(title, fontsize=14, pad=15)
    ax.set_ylabel("")
    ax.set_xlabel("Deviation from Target (%)", fontsize=12)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.legend(loc="upper right")

    if own_ax:
        fig.tight_layout()
        return fig
    return ax


def plot_attributed_deficit(df, time_col="time", mode_col="current_mode", extraction_col="TrueOreExtraction_Level", 
                            ideal_rate_per_day=6000.0, title="Cumulative Production Deficit by Mode", ax=None, palette=None):
    """
    Calculates the instantaneous lost production at each time step and attributes it
    to the active operating mode. Plots a stacked area chart so you can see exactly
    WHY production was lost (e.g., Unavoidable Shutdowns vs. Avoidable Contingencies).
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 6))
        own_ax = True
    else:
        own_ax = False

    # 1. Calculate time delta (dt) and extraction delta for each step looking forward
    dt = df[time_col].diff().shift(-1).fillna(0)
    actual_extraction_step = df[extraction_col].diff().shift(-1).fillna(0)
    
    # 2. Calculate ideal extraction for that step, and find the deficit
    ideal_extraction_step = dt * ideal_rate_per_day
    step_deficit = ideal_extraction_step - actual_extraction_step
    
    # Prevent negative deficits (in case surging pushes throughput slightly over temporarily)
    step_deficit = step_deficit.clip(lower=0)
    
    # 3. Create a DataFrame of just the deficits and modes
    deficit_df = pd.DataFrame({
        'time': df[time_col],
        'mode': df[mode_col].astype(str),
        'deficit': step_deficit
    })
    
    # 4. Pivot the data to group cumulative deficits by mode
    # We want columns for each mode, and rows for time
    pivot_df = deficit_df.pivot_table(index='time', columns='mode', values='deficit', aggfunc='sum').fillna(0)
    
    # Calculate the cumulative sum over time
    cumulative_pivot = pivot_df.cumsum()
    
    # Ensure Shutdown is plotted at the bottom (as the baseline unavoidable deficit)
    cols = list(cumulative_pivot.columns)
    shutdown_mode = next((c for c in cols if "SHUTDOWN" in str(c).upper()), None)
    if shutdown_mode and shutdown_mode in cols:
        cols.remove(shutdown_mode)
        cols = [shutdown_mode] + cols
        
    import matplotlib
    cmap = matplotlib.colormaps["tab10"]
    palette = palette or {}
    colors = []
    for idx, c in enumerate(cols):
        mode_name = str(c).split('.')[-1].upper()
        if mode_name in palette:
            colors.append(palette[mode_name])
        else:
            colors.append(cmap(idx % 10))
    
    # 5. Plot as a stacked area chart
    # Use a dictionary to map your modes to specific colors if desired, or use a colormap
    cumulative_pivot[cols].plot.area(ax=ax, alpha=0.8, linewidth=0, color=colors)

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("Simulation Time (Days)")
    ax.set_ylabel("Cumulative Lost Tonnage")
    
    # Clean up the legend
    handles, labels = ax.get_legend_handles_labels()
    # Clean up enum strings (e.g., "MineMode.SHUTDOWN" -> "SHUTDOWN")
    clean_labels = [str(l).split('.')[-1] for l in labels]
    ax.legend(handles, clean_labels, loc='upper left')

    if own_ax:
        fig.tight_layout()
        return fig
    return ax

def plot_deficit_disparity(df, time_col="time", mode_col="current_mode", extraction_col="TrueOreExtraction_Level", ideal_rate=6000.0, title="Mode Efficiency (Time Spent vs. Deficit Caused)", ax=None, verbose=True):
    """
    Shows the disproportionate impact of modes by comparing the % of total time spent 
    in a mode against the % of the total deficit it caused.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    # 1. Calculate time deltas and actual extraction looking forward
    df = df.copy()
    df[mode_col] = df[mode_col].astype(str)
    df['dt'] = df[time_col].diff().shift(-1).fillna(0)
    df['dx'] = df[extraction_col].diff().shift(-1).fillna(0)
    
    # 2. Calculate instantaneous deficit
    df['ideal_dx'] = df['dt'] * ideal_rate
    df['deficit'] = (df['ideal_dx'] - df['dx']).clip(lower=0)
    
    # 3. Aggregate by Mode
    summary = df.groupby(mode_col).agg({'dt': 'sum', 'deficit': 'sum'})
    
    summary['% of Total Time'] = (summary['dt'] / summary['dt'].sum()) * 100
    summary['% of Total Deficit'] = (summary['deficit'] / summary['deficit'].sum()) * 100
    
    if verbose:
        print(f"\n--- {title} ---")
        print(summary[['% of Total Time', '% of Total Deficit']].round(1).to_string())
        print("-" * (8 + len(title)))

    # 4. Melt for Seaborn grouped bar plot
    melted = summary[['% of Total Time', '% of Total Deficit']].reset_index().melt(
        id_vars=mode_col, var_name="Metric", value_name="Percentage"
    )
    
    # Sort so the highest deficit causes are at the top
    order = summary.sort_values('% of Total Deficit', ascending=False).index
    
    sns.barplot(data=melted, y=mode_col, x="Percentage", hue="Metric", order=order, palette=["#1f77b4", "#d62728"], ax=ax)

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("Percentage (%)", fontsize=12)
    ax.set_ylabel("")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))

    if own_ax:
        fig.tight_layout()
        return fig
    return ax

def plot_geology_impact(df, time_col="time", mode_col="current_mode", extraction_col="TrueOreExtraction_Level", grade_col="percentage_of_ore2", ideal_rate=6000.0, bottleneck_mode="MODE_A", max_rate_ore1=3600, max_rate_ore2=2400, ax=None):
    """
    Plots the true Geological Bottleneck. 
    Uses forward-differencing to correctly align discrete event rates with their causal states.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    df = df.copy()
    
    # THE FIX: Forward differencing. Calculate the dt and dx for the state we are ABOUT to sit in.
    df['dt'] = df[time_col].diff().shift(-1)
    df['dx'] = df[extraction_col].diff().shift(-1)
    
    # Filter out instantaneous transitions (where dt is 0) to avoid division by zero
    valid_mask = df['dt'] > 0.001
    df = df[valid_mask].copy()
    
    # Calculate true forward rate
    df['rate'] = df['dx'] / df['dt']
    df['deficit_rate'] = (ideal_rate - df['rate']).clip(lower=0)
    
    # Filter for standard Bottleneck Mode
    mode_a = df[(df[mode_col].astype(str).str.contains(bottleneck_mode)) & 
                (~df[mode_col].astype(str).str.contains("CONTINGENCY|SURGING"))]
    
    ore1_grade_pct = 100.0 - mode_a[grade_col]
    
    # Scatter the actual data
    sns.scatterplot(x=ore1_grade_pct, y=mode_a['deficit_rate'], color="#2ca02c", 
                    alpha=0.7, s=50, label="Actual Lost Tonnage (Mode A)", ax=ax)
    
    # --- Calculate the Theoretical "V" Curve ---
    x_ideal = np.linspace(20, 90, 200) # Ore 1 percentage
    y_limit = []
    
    for pct1 in x_ideal:
        pct2 = 100.0 - pct1
        # How much rock to extract to get Ore 1?
        max_rate_for_ore1 = max_rate_ore1 / (pct1 / 100.0) if pct1 > 0 else float('inf')
        # How much rock to extract to get Ore 2?
        max_rate_for_ore2 = max_rate_ore2 / (pct2 / 100.0) if pct2 > 0 else float('inf')
        
        # The mine MUST respect the most restrictive bottleneck
        max_extraction = min(max_rate_for_ore1, max_rate_for_ore2)
        
        # Plant physically cannot exceed 6000
        max_extraction = min(max_extraction, 6000)
        
        # Deficit is Ideal - Max Extraction
        y_limit.append(ideal_rate - max_extraction)
        
    ax.plot(x_ideal, y_limit, color="black", linestyle="--", linewidth=2, label="Theoretical Geological Physics")

    ax.set_title("Geological Bottleneck (The 'V' Curve)", fontsize=14, pad=15)
    ax.set_xlabel("Ore 1 Grade in Current Parcel (%)", fontsize=12)
    ax.set_ylabel("Lost Production Rate (Tons/Day)", fontsize=12)
    
    # Add a marker at the "Perfect Blend"
    ax.plot([60], [0], marker='*', color='gold', markersize=15, markeredgecolor='black', label="Perfect Geological Blend (60/40)")
    
    ax.legend(loc="upper center")
    ax.grid(True, alpha=0.3)

    if own_ax:
        fig.tight_layout()
        return fig
    return ax

def plot_deficit_breakdown_bar(df, time_col="time", mode_col="current_mode", extraction_col="TrueOreExtraction_Level", ideal_rate_per_day=6000.0, title="Final Deficit Breakdown by Mode (%)", ax=None, palette=None, verbose=True):
    """
    Plots a horizontal bar chart of the final cumulative deficit, normalized to 
    show the percentage contribution of each mode to the total lost tonnage.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    # 1. Calculate deficit
    df = df.copy()
    df['dt'] = df[time_col].diff().shift(-1).fillna(0)
    df['dx'] = df[extraction_col].diff().shift(-1).fillna(0)
    df['deficit'] = ((df['dt'] * ideal_rate_per_day) - df['dx']).clip(lower=0)
    df['mode_str'] = df[mode_col].astype(str).apply(lambda x: x.split('.')[-1])

    # 2. Aggregate and calculate percentages
    summary = df.groupby('mode_str')['deficit'].sum()
    summary = summary[summary > 0].sort_values(ascending=True) # Ascending for horizontal bar (largest at top)
    total_deficit = summary.sum()
    
    if total_deficit > 0:
        summary_pct = (summary / total_deficit) * 100
    else:
        summary_pct = summary

    if verbose:
        print(f"\n--- {title} ---")
        for mode in summary.index[::-1]:
            print(f"{mode}: {summary[mode]:,.1f} t ({summary_pct[mode]:.1f}%)")
        print(f"TOTAL LOST: {total_deficit:,.1f} t")
        print("-" * (8 + len(title)))

    palette = palette or {}
    colors = [palette.get(m.upper(), "gray") for m in summary.index]

    # 4. Plot Horizontal Bar
    bars = ax.barh(summary.index, summary_pct.values, color=colors, edgecolor='black', alpha=0.8)
    
    # Styling
    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("% of Total Lost Tonnage", fontsize=12)
    ax.set_xlim(0, max(summary_pct.max() * 1.15, 100)) # Leave room for labels
    
    # Add values at the end of bars
    for bar in bars:
        width = bar.get_width()
        ax.annotate(f'{width:.1f}%',
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0),  # 5 points horizontal offset
                    textcoords="offset points",
                    ha='left', va='center', fontsize=11, fontweight='bold')

    # Add total deficit info
    ax.text(0.95, 0.05, f"Total Lost: {total_deficit:,.0f} t", 
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            ha='right', va='bottom', bbox=dict(facecolor='white', alpha=0.8))

    if own_ax:
        fig.tight_layout()
        return fig
    return ax

def plot_structural_vs_operational_deficit(df, time_col="time", mode_col="current_mode", extraction_col="TrueOreExtraction_Level", ideal_rate=6000.0, structural_modes=None, ax=None, verbose=True):
    """
    Separates the cumulative deficit into 'Unavoidable' (Geology/Shutdowns) 
    and 'Avoidable' (Control Logic / Blending Failures).
    This defines the exact ceiling of what an RL agent can realistically optimize.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    df = df.copy()
    df['dt'] = df[time_col].diff().shift(-1).fillna(0)
    df['dx'] = df[extraction_col].diff().shift(-1).fillna(0)
    df['deficit'] = ((df['dt'] * ideal_rate) - df['dx']).clip(lower=0)
    df['mode_str'] = df[mode_col].astype(str)

    # Define the Buckets
    structural_modes = structural_modes or []
    
    def classify_bucket(mode):
        if any(sm in mode for sm in structural_modes) and "CONTINGENCY" not in mode and "SURGING" not in mode:
            return "Structural (Unavoidable: Geology & Shutdowns)"
        else:
            return "Operational (Avoidable: Control Logic & Contingencies)"

    df['Deficit_Type'] = df['mode_str'].apply(classify_bucket)
    
    # Pivot and cumsum
    pivot = df.pivot_table(index=time_col, columns='Deficit_Type', values='deficit', aggfunc='sum').fillna(0)
    cumsum_pivot = pivot.cumsum()

    if verbose:
        title_str = "Structural vs. Operational Deficit"
        print(f"\n--- {title_str} ---")
        final_totals = cumsum_pivot.iloc[-1] if not cumsum_pivot.empty else {}
        for deficit_type, val in final_totals.items():
            print(f"{deficit_type}: {val:,.1f} t")
        print("-" * (8 + len(title_str)))

    # Plot (Structural on bottom, Operational on top)
    cols = sorted(list(cumsum_pivot.columns), reverse=True) # Ensure Structural is first
    cumsum_pivot[cols].plot.area(ax=ax, color=["gray", "firebrick"], alpha=0.7, linewidth=0)

    ax.set_title("Structural vs. Operational Deficit", fontsize=14, pad=15)
    ax.set_xlabel("Simulation Time (Days)", fontsize=12)
    ax.set_ylabel("Cumulative Lost Tonnage", fontsize=12)
    ax.legend(loc='upper left')

    # Add text explaining the RL Goal
    ax.text(0.5, 0.85, "RL Optimization Target:\nSquash the Red Layer to Zero", 
            transform=ax.transAxes, fontsize=12, color="firebrick", fontweight="bold",
            ha="center", bbox=dict(facecolor='white', alpha=0.8, edgecolor='firebrick'))

    if own_ax:
        fig.tight_layout()
        return fig
    return ax

def plot_normalized_cumulative_deficit(df, time_col="time", mode_col="current_mode", extraction_col="TrueOreExtraction_Level", ideal_rate_per_day=6000.0, title="Deficit Composition Over Time (100% Stacked)", ax=None, palette=None):
    """
    Plots the cumulative deficit normalized to 100% at each time step.
    Shows how the composition of the plant's inefficiency evolves over time.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 6))
        own_ax = True
    else:
        own_ax = False

    df = df.copy()
    df['dt'] = df[time_col].diff().shift(-1).fillna(0)
    df['dx'] = df[extraction_col].diff().shift(-1).fillna(0)
    df['deficit'] = ((df['dt'] * ideal_rate_per_day) - df['dx']).clip(lower=0)
    df['mode_str'] = df[mode_col].astype(str).apply(lambda x: x.split('.')[-1])

    # Pivot to get cumulative sums
    pivot_df = df.pivot_table(index=time_col, columns='mode_str', values='deficit', aggfunc='sum').fillna(0)
    cumulative_pivot = pivot_df.cumsum()

    # Normalize to 100% (Divide each row by its sum)
    row_sums = cumulative_pivot.sum(axis=1)
    # Avoid division by zero at the very start
    normalized_pivot = cumulative_pivot.div(row_sums.replace(0, 1), axis=0) * 100

    # Order columns and assign colors
    cols = list(normalized_pivot.columns)
    if "SHUTDOWN" in cols:
        cols.remove("SHUTDOWN")
        cols = ["SHUTDOWN"] + cols
        
    palette = palette or {}
    colors = [palette.get(c.upper(), "gray") for c in cols]
    
    # Plot
    normalized_pivot[cols].plot.area(ax=ax, alpha=0.8, linewidth=0, color=colors)

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("Simulation Time (Days)", fontsize=12)
    ax.set_ylabel("% of Total Cumulative Deficit", fontsize=12)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1))

    if own_ax:
        fig.tight_layout()
        return fig
    return ax

def plot_structural_vs_operational_by_mode(df, time_col="time", mode_col="current_mode", extraction_col="TrueOreExtraction_Level", ideal_rate=6000.0, title="Structural vs. Operational Deficit by Base Mode", structural_modes=None, base_mode_mapper=None, ax=None, verbose=True):
    """
    Groups deficits by Base Mode (Mode A, Mode B, Shutdown) and stacks them by 
    whether the deficit was Structural (Unavoidable) or Operational (Avoidable via RL).
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
        own_ax = True
    else:
        own_ax = False

    df = df.copy()
    df['dt'] = df[time_col].diff().shift(-1).fillna(0)
    df['dx'] = df[extraction_col].diff().shift(-1).fillna(0)
    df['deficit'] = ((df['dt'] * ideal_rate) - df['dx']).clip(lower=0)
    df['mode_str'] = df[mode_col].astype(str).apply(lambda x: x.split('.')[-1])

    structural_modes = structural_modes or []

    # 1. Map to Base Modes
    def get_base_mode(m):
        if base_mode_mapper:
            return base_mode_mapper(m)
        return m.split('_CONTINGENCY')[0].split('_MINE')[0] # generic fallback

    # 2. Map to Deficit Type
    def get_deficit_type(m):
        # Pure geological/shutdowns are Structural
        if any(sm in m for sm in structural_modes) and "CONTINGENCY" not in m and "SURGING" not in m: 
            return "Structural (Unavoidable)"
        # Contingencies, Surging, and others are Operational
        return "Operational (Avoidable)"

    df['Base_Mode'] = df['mode_str'].apply(get_base_mode)
    df['Deficit_Type'] = df['mode_str'].apply(get_deficit_type)

    # 3. Aggregate
    summary = df.groupby(['Base_Mode', 'Deficit_Type'])['deficit'].sum().unstack(fill_value=0)
    
    # Ensure both columns exist even if one is empty
    for col in ["Structural (Unavoidable)", "Operational (Avoidable)"]:
        if col not in summary.columns:
            summary[col] = 0

    if verbose:
        print(f"\n--- {title} ---")
        print(summary.round(1).to_string())
        print("-" * (8 + len(title)))

    # 4. Plot as a Stacked Bar Chart
    # Sort order to keep it logical (if we know the keys, otherwise alphabetical)
    order = sorted(df['Base_Mode'].unique())
    summary = summary.reindex(order).fillna(0)

    # Reorder columns to ensure consistent stacking order
    col_order = ["Operational (Avoidable)", "Structural (Unavoidable)"]
    summary = summary[[c for c in col_order if c in summary.columns]]

    summary.plot(kind='bar', stacked=True, color=["firebrick", "gray"], ax=ax, alpha=0.85, edgecolor='black')

    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel("")
    ax.set_ylabel("Total Lost Tonnage", fontsize=12)
    ax.tick_params(axis='x', rotation=0, labelsize=11)
    
    # Format Y axis with commas for thousands
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    
    ax.legend(title="Deficit Classification", loc="upper left")

    if own_ax:
        fig.tight_layout()
        return fig
    return ax
