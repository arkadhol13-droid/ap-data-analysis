
import numpy as np
import pandas as pd

AGG_FUNCS = {
    "Sum": "sum",
    "Average": "mean",
    "Count": "count",
    "Max": "max",
    "Min": "min",
}

MAX_CATEGORICAL_UNIQUE = 200  # above this, a column is treated as free text, not a filterable category


def clean_numeric_like_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Real-world data from any sector often has numbers formatted as text:
    "₹1,20,000", "$45.5K", "72%", "N/A". Without this, such columns get
    misclassified as categorical/text and are invisible to the numeric
    analysis engine. For every object column where most values look
    numeric once symbols/commas are stripped, converts the whole column
    to numeric. Columns that are genuinely text (names, categories) are
    left untouched because they won't pass the "mostly numeric" check.
    """
    df = df.copy()
    bad_tokens = r"(?i)^\s*(inf|-inf|\+inf|infinity|-infinity|nan|none|null|na|n/a|-)\s*$"

    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().astype(str).head(200)
        if sample.empty:
            continue
        cleaned_sample = sample.str.replace(r"[₹$€£,%\s]", "", regex=True)
        cleaned_sample = cleaned_sample.mask(cleaned_sample.str.match(bad_tokens, na=False), np.nan)
        numeric_sample = pd.to_numeric(cleaned_sample, errors="coerce")

        if numeric_sample.notna().mean() >= 0.85:
            full_cleaned = df[col].astype(str).str.replace(r"[₹$€£,%\s]", "", regex=True)
            full_cleaned = full_cleaned.mask(full_cleaned.str.match(bad_tokens, na=False), np.nan)
            df[col] = pd.to_numeric(full_cleaned, errors="coerce")

    return df


def detect_column_types(df: pd.DataFrame) -> dict:
    """
    Classifies every column as 'date', 'numeric', or 'categorical' so the
    filter panel and aggregation controls can offer the right widget for
    each one, without the user having to specify types manually.
    """
    types = {}
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            types[col] = "date"
        elif pd.api.types.is_numeric_dtype(series):
            types[col] = "numeric"
        elif series.nunique(dropna=True) <= MAX_CATEGORICAL_UNIQUE:
            types[col] = "categorical"
        else:
            types[col] = "text"  # too high-cardinality to filter/group usefully
    return types


def auto_parse_dates(df: pd.DataFrame, sample_size: int = 200) -> pd.DataFrame:
    """
    Attempts to auto-detect object columns that actually contain dates
    (e.g. "2026-01-15" stored as text) and converts them, so the filter
    panel can offer a date-range slicer instead of treating them as plain
    categories. Only converts a column if the large majority of a sample
    parses successfully, to avoid false positives on genuinely text data.
    """
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().head(sample_size)
        if sample.empty:
            continue
        parsed_sample = pd.to_datetime(sample, errors="coerce")
        if parsed_sample.notna().mean() >= 0.85:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    filters: {column_name: value}
      - value is a (min, max) tuple  -> numeric or date range filter
      - value is a list              -> categorical "isin" filter
    Empty/None values are treated as "no filter on this column".
    """
    filtered = df
    for col, value in filters.items():
        if col not in filtered.columns or value is None:
            continue
        if isinstance(value, tuple) and len(value) == 2:
            lo, hi = value
            filtered = filtered[(filtered[col] >= lo) & (filtered[col] <= hi)]
        elif isinstance(value, list) and len(value) > 0:
            filtered = filtered[filtered[col].isin(value)]
    return filtered


def aggregate(df: pd.DataFrame, group_by: str, measure: str, agg_label: str) -> pd.DataFrame:
    """
    Core "smart aggregation" used by every chart in the multi-chart grid:
    Group By column + Measure column + Aggregation function -> a tidy,
    sorted dataframe ready to plot. Mirrors the Field/Values/Summarize-by
    pattern from Power BI and Tableau.
    """
    func = AGG_FUNCS.get(agg_label, "sum")

    working = df.copy()
    if func != "count":
        working[measure] = pd.to_numeric(working[measure], errors="coerce")

    if group_by is None or group_by == measure:
        value = working[measure].agg(func) if func != "count" else working[measure].count()
        return pd.DataFrame({measure: [value]})

    grouped = (
        working.groupby(group_by, dropna=False)[measure]
        .agg(func)
        .reset_index()
        .sort_values(measure, ascending=False)
    )
    return grouped


def compute_kpi(df: pd.DataFrame, measure: str, agg_label: str, date_col: str = None) -> dict:
    """
    Computes a KPI's headline value plus a period-over-period trend:
    - Splits the (optionally date-sorted) data into an earlier half and a
      later half, aggregates each half with the same function, and
      reports the % change -- this is the "vs previous period" comparison
      every BI tool's KPI card shows.
    - Also returns a short series suitable for a sparkline.
    Falls back gracefully (no trend) on tiny or all-missing data instead
    of raising, since this only ever feeds a display card.
    """
    func = AGG_FUNCS.get(agg_label, "sum")

    ordered = df.sort_values(date_col) if date_col and date_col in df.columns else df

    values = pd.to_numeric(ordered[measure], errors="coerce") if func != "count" else ordered[measure]
    values = values.dropna() if func != "count" else values

    if len(values) == 0:
        return {"value": 0, "delta_pct": None, "trend": "flat", "sparkline": []}

    current_value = values.agg(func) if func != "count" else values.count()

    half = len(values) // 2
    if half == 0:
        return {
            "value": current_value,
            "delta_pct": None,
            "trend": "flat",
            "sparkline": values.tolist()[-30:],
        }

    first_half, second_half = values.iloc[:half], values.iloc[half:]
    v1 = first_half.agg(func) if func != "count" else first_half.count()
    v2 = second_half.agg(func) if func != "count" else second_half.count()

    if v1 in (0, None) or pd.isna(v1):
        delta_pct = None
    else:
        delta_pct = ((v2 - v1) / abs(v1)) * 100

    if delta_pct is None or abs(delta_pct) < 0.5:
        trend = "flat"
    else:
        trend = "up" if delta_pct > 0 else "down"

    return {
        "value": current_value,
        "delta_pct": delta_pct,
        "trend": trend,
        "sparkline": values.tolist()[-30:],
    }


def can_build_3d(col_types: dict) -> bool:
    """Whether this dataset has enough shape (1+ dimension, 2+ metrics)
    for a 3D chart to actually add value over a 2D one."""
    dimensions = [c for c, t in col_types.items() if t == "categorical"]
    metrics = [c for c, t in col_types.items() if t == "numeric"]
    return bool(dimensions) and len(metrics) >= 2


def build_3d_scatter(df: pd.DataFrame, dimension_col: str, metric_x: str, metric_y: str, metric_z: str = None):
    """
    Builds an interactive, rotatable 3D scatter: one point per category
    in `dimension_col`, positioned by the aggregated totals of metric_x/
    metric_y/metric_z (e.g. City x Sales x Profit). Falls back to using
    the category's rank as the Z axis when only two metrics are picked,
    so the chart is still meaningfully 3D rather than a flat plane.
    Returns (figure, grouped_dataframe) or (None, None) if there isn't
    enough usable data.
    """
    import plotly.graph_objects as go

    cols = [dimension_col, metric_x, metric_y] + ([metric_z] if metric_z else [])
    working = df[cols].copy()
    working[metric_x] = pd.to_numeric(working[metric_x], errors="coerce")
    working[metric_y] = pd.to_numeric(working[metric_y], errors="coerce")

    agg = {metric_x: "sum", metric_y: "sum"}
    if metric_z:
        working[metric_z] = pd.to_numeric(working[metric_z], errors="coerce")
        agg[metric_z] = "sum"

    grouped = working.dropna(subset=[metric_x, metric_y]).groupby(dimension_col, dropna=False).agg(agg).reset_index()
    if grouped.empty:
        return None, None

    if metric_z:
        z_values = grouped[metric_z]
        z_label = metric_z
    else:
        grouped = grouped.sort_values(metric_x, ascending=False).reset_index(drop=True)
        z_values = grouped.index + 1
        z_label = f"Rank by {metric_x}"

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=grouped[metric_x],
                y=grouped[metric_y],
                z=z_values,
                mode="markers+text",
                text=grouped[dimension_col],
                textposition="top center",
                textfont=dict(size=10, color="#E2E8F0"),
                marker=dict(
                    size=9,
                    color=z_values,
                    colorscale="Viridis",
                    showscale=True,
                    opacity=0.9,
                    line=dict(width=0.5, color="#0F172A"),
                ),
                hovertemplate=(
                    f"<b>%{{text}}</b><br>{metric_x}: %{{x:,.2f}}<br>"
                    f"{metric_y}: %{{y:,.2f}}<br>{z_label}: %{{z:,.2f}}<extra></extra>"
                ),
            )
        ]
    )

    fig.update_layout(
        scene=dict(
            xaxis_title=metric_x,
            yaxis_title=metric_y,
            zaxis_title=z_label,
            xaxis=dict(backgroundcolor="#0F172A", gridcolor="#233047"),
            yaxis=dict(backgroundcolor="#0F172A", gridcolor="#233047"),
            zaxis=dict(backgroundcolor="#0F172A", gridcolor="#233047"),
        ),
        template="plotly_dark",
        height=520,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    return fig, grouped


_BAR_PALETTE = [
    "#7c3aed", "#38bdf8", "#f472b6", "#fbbf24", "#34d399",
    "#f87171", "#c084fc", "#60a5fa", "#facc15", "#4ade80",
]


def _cuboid_mesh(cx, cy, width, depth, height, color, name):
    """Builds one solid, colorful 3D bar (a rectangular box) as a
    go.Mesh3d trace -- this is what makes the chart read as an actual
    3D bar/column chart instead of floating dots. cx/cy is the bar's
    footprint center; the bar rises from z=0 to z=height."""
    import plotly.graph_objects as go

    x0, x1 = cx - width / 2, cx + width / 2
    y0, y1 = cy - depth / 2, cy + depth / 2
    z0, z1 = 0, height

    xs = [x0, x1, x1, x0, x0, x1, x1, x0]
    ys = [y0, y0, y1, y1, y0, y0, y1, y1]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]

    # 12 triangles covering the 6 faces of the box.
    i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    k = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]

    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i, j=j, k=k,
        color=color, opacity=0.92, flatshading=True,
        name=name, showlegend=False, hoverinfo="skip",
        lighting=dict(ambient=0.55, diffuse=0.7, specular=0.4, roughness=0.4),
        lightposition=dict(x=100, y=200, z=300),
    )


def build_3d_bar_chart(df: pd.DataFrame, dimension_col: str, metric_height: str, metric_spread: str = None):
    """
    A real 3D bar/column chart: one solid colorful cuboid per category,
    positioned on a grid and rising to a height driven by metric_height.
    When metric_spread is given, bars are additionally spread out along
    the Y axis by that metric's value (e.g. City on X, Profit spread on
    Y, Sales as bar height on Z) so the chart carries two metrics of
    meaning, not just one. Falls back to an even grid on Y when no
    second metric is picked. Returns (figure, grouped_dataframe) or
    (None, None) if there's no usable data.
    """
    import plotly.graph_objects as go

    cols = [dimension_col, metric_height] + ([metric_spread] if metric_spread else [])
    working = df[cols].copy()
    working[metric_height] = pd.to_numeric(working[metric_height], errors="coerce")

    agg = {metric_height: "sum"}
    if metric_spread:
        working[metric_spread] = pd.to_numeric(working[metric_spread], errors="coerce")
        agg[metric_spread] = "sum"

    grouped = working.dropna(subset=[metric_height]).groupby(dimension_col, dropna=False).agg(agg).reset_index()
    if grouped.empty:
        return None, None

    grouped = grouped.sort_values(metric_height, ascending=False).reset_index(drop=True)
    n = len(grouped)

    max_height = grouped[metric_height].max() or 1
    bar_width = 0.6

    if metric_spread:
        y_positions = grouped[metric_spread].tolist()
        y_label = metric_spread
        y_span = (max(y_positions) - min(y_positions)) or 1
        bar_depth = max(y_span / max(n, 1) * 0.5, y_span * 0.04)
    else:
        y_positions = [0] * n
        y_label = ""
        bar_depth = bar_width

    traces = []
    hover_x, hover_y, hover_z, hover_text = [], [], [], []

    for idx, row in grouped.iterrows():
        color = _BAR_PALETTE[idx % len(_BAR_PALETTE)]
        cx = idx
        cy = y_positions[idx]
        height = float(row[metric_height])
        traces.append(_cuboid_mesh(cx, cy, bar_width, bar_depth, height, color, str(row[dimension_col])))

        hover_x.append(cx)
        hover_y.append(cy)
        hover_z.append(height + max_height * 0.04)
        text = f"<b>{row[dimension_col]}</b><br>{metric_height}: {row[metric_height]:,.2f}"
        if metric_spread:
            text += f"<br>{metric_spread}: {row[metric_spread]:,.2f}"
        hover_text.append(text)

    # Invisible marker layer on top of each bar just to carry rich hover
    # tooltips -- Mesh3d itself doesn't support this cleanly per-bar.
    hover_layer = go.Scatter3d(
        x=hover_x, y=hover_y, z=hover_z,
        mode="markers",
        marker=dict(size=4, color="rgba(0,0,0,0)"),
        hovertext=hover_text,
        hoverinfo="text",
        showlegend=False,
    )

    fig = go.Figure(data=traces + [hover_layer])

    fig.update_layout(
        scene=dict(
            xaxis=dict(
                title=dimension_col,
                tickmode="array",
                tickvals=list(range(n)),
                ticktext=grouped[dimension_col].astype(str).tolist(),
                backgroundcolor="#0F172A", gridcolor="#233047",
            ),
            yaxis=dict(title=y_label, backgroundcolor="#0F172A", gridcolor="#233047"),
            zaxis=dict(title=metric_height, backgroundcolor="#0F172A", gridcolor="#233047"),
            camera=dict(eye=dict(x=1.5, y=-1.5, z=0.9)),
        ),
        template="plotly_dark",
        height=520,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )

    return fig, grouped

# 3D STACKED BAR

def build_3d_stacked_bar(df: pd.DataFrame, dimension_col: str, metric_cols: list):
    """
    One bar per category, made of stacked colored segments -- one
    segment per metric in metric_cols, each a separate cuboid stacked on
    top of the last. e.g. Region on X, [Product A Sales, Product B
    Sales, Product C Sales] stacked as segments of the same bar.
    """
    import plotly.graph_objects as go

    cols = [dimension_col] + metric_cols
    working = df[cols].copy()
    for m in metric_cols:
        working[m] = pd.to_numeric(working[m], errors="coerce")

    grouped = working.dropna(subset=metric_cols, how="all").groupby(dimension_col, dropna=False)[metric_cols].sum().reset_index()
    if grouped.empty:
        return None, None

    grouped["__total__"] = grouped[metric_cols].sum(axis=1)
    grouped = grouped.sort_values("__total__", ascending=False).reset_index(drop=True)
    n = len(grouped)
    bar_width = bar_depth = 0.6

    traces = []
    hover_x, hover_y, hover_z, hover_text = [], [], [], []

    for idx, row in grouped.iterrows():
        z_base = 0.0
        for m_i, metric in enumerate(metric_cols):
            seg_height = float(row[metric]) if pd.notna(row[metric]) else 0.0
            if seg_height <= 0:
                continue
            color = _BAR_PALETTE[m_i % len(_BAR_PALETTE)]
            traces.append(
                _cuboid_segment_mesh(idx, 0, bar_width, bar_depth, z_base, z_base + seg_height, color, f"{metric} - {row[dimension_col]}")
            )
            hover_x.append(idx)
            hover_y.append(0)
            hover_z.append(z_base + seg_height / 2)
            hover_text.append(f"<b>{row[dimension_col]}</b><br>{metric}: {seg_height:,.2f}")
            z_base += seg_height

    hover_layer = go.Scatter3d(
        x=hover_x, y=hover_y, z=hover_z, mode="markers",
        marker=dict(size=3, color="rgba(0,0,0,0)"),
        hovertext=hover_text, hoverinfo="text", showlegend=False,
    )

    # legend proxies -- one per metric, shown as flat 2D-style markers so
    # the color -> metric mapping is readable without adding real geometry.
    legend_traces = [
        go.Scatter3d(
            x=[None], y=[None], z=[None], mode="markers",
            marker=dict(size=8, color=_BAR_PALETTE[i % len(_BAR_PALETTE)]),
            name=metric, showlegend=True,
        )
        for i, metric in enumerate(metric_cols)
    ]

    fig = go.Figure(data=traces + [hover_layer] + legend_traces)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title=dimension_col, tickmode="array", tickvals=list(range(n)),
                       ticktext=grouped[dimension_col].astype(str).tolist(),
                       backgroundcolor="#0F172A", gridcolor="#233047"),
            yaxis=dict(title="", showticklabels=False, backgroundcolor="#0F172A", gridcolor="#233047"),
            zaxis=dict(title="Total", backgroundcolor="#0F172A", gridcolor="#233047"),
            camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9)),
        ),
        template="plotly_dark", height=520, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig, grouped


def _cuboid_segment_mesh(cx, cy, width, depth, z_bottom, z_top, color, name):
    """Same cuboid builder as _cuboid_mesh but with an explicit z-range,
    used to stack multiple segments into one bar."""
    import plotly.graph_objects as go

    x0, x1 = cx - width / 2, cx + width / 2
    y0, y1 = cy - depth / 2, cy + depth / 2

    xs = [x0, x1, x1, x0, x0, x1, x1, x0]
    ys = [y0, y0, y1, y1, y0, y0, y1, y1]
    zs = [z_bottom] * 4 + [z_top] * 4

    i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    k = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]

    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i, j=j, k=k,
        color=color, opacity=0.92, flatshading=True,
        name=name, showlegend=False, hoverinfo="skip",
        lighting=dict(ambient=0.55, diffuse=0.7, specular=0.4, roughness=0.4),
        lightposition=dict(x=100, y=200, z=300),
    )

# 3D DONUT

def build_3d_donut(df: pd.DataFrame, dimension_col: str, metric_col: str):
    """
    A real extruded 3D donut: each category becomes a colored wedge of a
    ring, with angular span proportional to its share of the total. Built
    from scratch with Mesh3d (Plotly has no native 3D pie/donut).
    """
    import numpy as np
    import plotly.graph_objects as go

    working = df[[dimension_col, metric_col]].copy()
    working[metric_col] = pd.to_numeric(working[metric_col], errors="coerce")
    grouped = working.dropna().groupby(dimension_col, dropna=False)[metric_col].sum().reset_index()
    grouped = grouped[grouped[metric_col] > 0].sort_values(metric_col, ascending=False).reset_index(drop=True)
    if grouped.empty:
        return None, None

    total = grouped[metric_col].sum()
    inner_r, outer_r, thickness = 0.55, 1.0, 0.35
    traces = []
    hover_x, hover_y, hover_z, hover_text = [], [], [], []
    angle = 0.0

    for idx, row in grouped.iterrows():
        share = float(row[metric_col]) / total
        span = share * 2 * np.pi * 0.995  # tiny gap between wedges
        color = _BAR_PALETTE[idx % len(_BAR_PALETTE)]
        traces.append(_donut_wedge_mesh(angle, angle + span, inner_r, outer_r, thickness, color))

        mid_angle = angle + span / 2
        mid_r = (inner_r + outer_r) / 2
        hover_x.append(mid_r * np.cos(mid_angle))
        hover_y.append(mid_r * np.sin(mid_angle))
        hover_z.append(thickness + 0.05)
        hover_text.append(f"<b>{row[dimension_col]}</b><br>{metric_col}: {row[metric_col]:,.2f} ({share*100:.1f}%)")
        angle += span

    hover_layer = go.Scatter3d(
        x=hover_x, y=hover_y, z=hover_z, mode="markers",
        marker=dict(size=4, color="rgba(0,0,0,0)"),
        hovertext=hover_text, hoverinfo="text", showlegend=False,
    )
    legend_traces = [
        go.Scatter3d(
            x=[None], y=[None], z=[None], mode="markers",
            marker=dict(size=8, color=_BAR_PALETTE[i % len(_BAR_PALETTE)]),
            name=str(row[dimension_col]), showlegend=True,
        )
        for i, row in grouped.iterrows()
    ]

    fig = go.Figure(data=traces + [hover_layer] + legend_traces)
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False, backgroundcolor="#0F172A"),
            yaxis=dict(visible=False, backgroundcolor="#0F172A"),
            zaxis=dict(visible=False, backgroundcolor="#0F172A"),
            camera=dict(eye=dict(x=0.9, y=-0.9, z=1.4)),
            aspectmode="cube",
        ),
        template="plotly_dark", height=520, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig, grouped


def _donut_wedge_mesh(theta0, theta1, inner_r, outer_r, thickness, color, segments=8):
    """Extrudes one ring wedge (a donut slice) between angles theta0/theta1
    into a solid 3D block by building top+bottom rings and connecting them
    with side faces -- the actual geometry behind the 3D donut chart."""
    import numpy as np
    import plotly.graph_objects as go

    thetas = np.linspace(theta0, theta1, segments)
    xs, ys, zs = [], [], []

    # bottom ring (inner then outer), then top ring (inner then outer)
    for z in (0, thickness):
        for r in (inner_r, outer_r):
            for t in thetas:
                xs.append(r * np.cos(t))
                ys.append(r * np.sin(t))
                zs.append(z)

    n = segments
    # index blocks: 0..n-1 = bottom-inner, n..2n-1 = bottom-outer,
    # 2n..3n-1 = top-inner, 3n..4n-1 = top-outer
    i_idx, j_idx, k_idx = [], [], []

    def quad(a, b, c, d):
        i_idx.extend([a, a]); j_idx.extend([b, c]); k_idx.extend([c, d])

    for s in range(n - 1):
        bi, bo = s, n + s
        bi2, bo2 = s + 1, n + s + 1
        ti, to = 2 * n + s, 3 * n + s
        ti2, to2 = 2 * n + s + 1, 3 * n + s + 1

        quad(bi, bo, bo2, bi2)      # bottom face strip
        quad(ti, to, to2, ti2)      # top face strip
        quad(bi, ti, ti2, bi2)      # inner wall strip
        quad(bo, to, to2, bo2)      # outer wall strip

    # end caps (flat radial faces at theta0 and theta1)
    quad(0, n, 3 * n, 2 * n)
    quad(n - 1, 2 * n - 1, 4 * n - 1, 3 * n - 1)

    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i_idx, j=j_idx, k=k_idx,
        color=color, opacity=0.95, flatshading=True,
        showlegend=False, hoverinfo="skip",
        lighting=dict(ambient=0.6, diffuse=0.65, specular=0.3, roughness=0.5),
        lightposition=dict(x=100, y=200, z=300),
    )

# 3D SURFACE (trend of each category over time)

def build_3d_surface(df: pd.DataFrame, date_col: str, dimension_col: str, metric_col: str, top_n_categories: int = 8):
    """
    A true Plotly Surface: rows = time period, columns = category, height
    = metric value. Shows how every category's metric evolved over time
    as one continuous folded sheet -- e.g. "Sales surface across Region
    over Month". Limited to the top N categories by total value so the
    surface stays readable.
    """
    import plotly.graph_objects as go

    working = df[[date_col, dimension_col, metric_col]].copy()
    working[metric_col] = pd.to_numeric(working[metric_col], errors="coerce")
    working[date_col] = pd.to_datetime(working[date_col], errors="coerce")
    working = working.dropna(subset=[date_col, metric_col])
    if working.empty:
        return None, None

    top_categories = (
        working.groupby(dimension_col)[metric_col].sum().sort_values(ascending=False).head(top_n_categories).index
    )
    working = working[working[dimension_col].isin(top_categories)]

    pivot = working.pivot_table(index=date_col, columns=dimension_col, values=metric_col, aggfunc="sum", fill_value=0)
    pivot = pivot.sort_index()
    if pivot.empty or pivot.shape[0] < 2 or pivot.shape[1] < 2:
        return None, None

    fig = go.Figure(
        data=[
            go.Surface(
                z=pivot.values,
                x=list(pivot.columns.astype(str)),
                y=[d.strftime("%d %b %Y") for d in pivot.index],
                colorscale="Viridis",
                colorbar=dict(title=metric_col),
            )
        ]
    )
    fig.update_layout(
        scene=dict(
            xaxis=dict(title=dimension_col, backgroundcolor="#0F172A", gridcolor="#233047"),
            yaxis=dict(title=date_col, backgroundcolor="#0F172A", gridcolor="#233047"),
            zaxis=dict(title=metric_col, backgroundcolor="#0F172A", gridcolor="#233047"),
            camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9)),
        ),
        template="plotly_dark", height=520, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig, pivot

# 3D BUBBLE

def build_3d_bubble(df: pd.DataFrame, dimension_col: str, metric_x: str, metric_y: str, metric_size: str):
    """Like the 3D scatter, but marker size is driven by a third metric --
    the classic 'bubble chart' pattern extended into 3D space."""
    import plotly.graph_objects as go

    cols = [dimension_col, metric_x, metric_y, metric_size]
    working = df[cols].copy()
    for m in (metric_x, metric_y, metric_size):
        working[m] = pd.to_numeric(working[m], errors="coerce")

    grouped = working.dropna().groupby(dimension_col, dropna=False).agg(
        {metric_x: "sum", metric_y: "sum", metric_size: "sum"}
    ).reset_index()
    if grouped.empty:
        return None, None

    size_series = grouped[metric_size].clip(lower=0)
    max_size = size_series.max() or 1
    marker_sizes = 10 + (size_series / max_size) * 40  # scale into a readable pixel range

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=grouped[metric_x], y=grouped[metric_y], z=grouped[metric_size],
                mode="markers+text",
                text=grouped[dimension_col],
                textposition="top center",
                textfont=dict(size=10, color="#E2E8F0"),
                marker=dict(
                    size=marker_sizes, color=grouped[metric_size], colorscale="Plasma",
                    showscale=True, opacity=0.85, line=dict(width=0.5, color="#0F172A"),
                ),
                hovertemplate=(
                    f"<b>%{{text}}</b><br>{metric_x}: %{{x:,.2f}}<br>"
                    f"{metric_y}: %{{y:,.2f}}<br>{metric_size}: %{{z:,.2f}}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        scene=dict(
            xaxis_title=metric_x, yaxis_title=metric_y, zaxis_title=metric_size,
            xaxis=dict(backgroundcolor="#0F172A", gridcolor="#233047"),
            yaxis=dict(backgroundcolor="#0F172A", gridcolor="#233047"),
            zaxis=dict(backgroundcolor="#0F172A", gridcolor="#233047"),
        ),
        template="plotly_dark", height=520, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig, grouped

# 3D LINE TREND (per-category trajectory over time)

def build_3d_line_trend(df: pd.DataFrame, date_col: str, dimension_col: str, metric_col: str, top_n_categories: int = 6):
    """
    One connected 3D line per category: X = time, Y = category (spread out
    so lines don't overlap), Z = metric value. Lets you compare several
    categories' trends at once in a single 3D view instead of an
    overlapping 2D line chart. Limited to the top N categories by total
    value for readability.
    """
    import plotly.graph_objects as go

    working = df[[date_col, dimension_col, metric_col]].copy()
    working[metric_col] = pd.to_numeric(working[metric_col], errors="coerce")
    working[date_col] = pd.to_datetime(working[date_col], errors="coerce")
    working = working.dropna(subset=[date_col, metric_col]).sort_values(date_col)
    if working.empty:
        return None, None

    top_categories = (
        working.groupby(dimension_col)[metric_col].sum().sort_values(ascending=False).head(top_n_categories).index.tolist()
    )

    traces = []
    for idx, category in enumerate(top_categories):
        subset = working[working[dimension_col] == category]
        if subset.empty:
            continue
        color = _BAR_PALETTE[idx % len(_BAR_PALETTE)]
        traces.append(
            go.Scatter3d(
                x=subset[date_col], y=[idx] * len(subset), z=subset[metric_col],
                mode="lines+markers", name=str(category),
                line=dict(color=color, width=4),
                marker=dict(size=3, color=color),
                hovertemplate=f"<b>{category}</b><br>%{{x}}<br>{metric_col}: %{{z:,.2f}}<extra></extra>",
            )
        )

    if not traces:
        return None, None

    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title=date_col, backgroundcolor="#0F172A", gridcolor="#233047"),
            yaxis=dict(
                title=dimension_col, tickmode="array", tickvals=list(range(len(top_categories))),
                ticktext=[str(c) for c in top_categories], backgroundcolor="#0F172A", gridcolor="#233047",
            ),
            zaxis=dict(title=metric_col, backgroundcolor="#0F172A", gridcolor="#233047"),
            camera=dict(eye=dict(x=1.7, y=-1.5, z=0.8)),
        ),
        template="plotly_dark", height=520, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig, working

# 3D TARGET / GAP VISUALIZATION

def build_3d_target_chart(df: pd.DataFrame, dimension_col: str, metric_col: str, target_value: float):
    """
    "Current -> Gap -> Target" per category: a solid bar up to the current
    value (green if it meets/exceeds target, red if below), with a
    translucent wireframe-style plane marking the target height across
    the whole scene so every bar's gap to target is visible at a glance.
    """
    import plotly.graph_objects as go

    working = df[[dimension_col, metric_col]].copy()
    working[metric_col] = pd.to_numeric(working[metric_col], errors="coerce")
    grouped = working.dropna().groupby(dimension_col, dropna=False)[metric_col].sum().reset_index()
    if grouped.empty:
        return None, None

    grouped = grouped.sort_values(metric_col, ascending=False).reset_index(drop=True)
    n = len(grouped)
    bar_width = bar_depth = 0.6

    traces = []
    hover_x, hover_y, hover_z, hover_text = [], [], [], []

    for idx, row in grouped.iterrows():
        current = float(row[metric_col])
        met_target = current >= target_value
        color = "#34d399" if met_target else "#f87171"
        traces.append(_cuboid_mesh(idx, 0, bar_width, bar_depth, current, color, str(row[dimension_col])))

        gap = target_value - current
        hover_x.append(idx)
        hover_y.append(0)
        hover_z.append(current + max(target_value, current) * 0.05)
        status = "Target met ✅" if met_target else f"Gap: {gap:,.2f}"
        hover_text.append(f"<b>{row[dimension_col]}</b><br>Current: {current:,.2f}<br>Target: {target_value:,.2f}<br>{status}")

    max_val = max(grouped[metric_col].max(), target_value) * 1.15
    plane_x = [-0.7, n - 0.3, n - 0.3, -0.7]
    plane_y = [-1, -1, 1, 1]
    plane_z = [target_value] * 4
    target_plane = go.Mesh3d(
        x=plane_x, y=plane_y, z=plane_z,
        i=[0], j=[1], k=[2],
        color="#facc15", opacity=0.25, name="Target", showlegend=True, hoverinfo="skip",
    )
    target_plane_2 = go.Mesh3d(
        x=plane_x, y=plane_y, z=plane_z,
        i=[0], j=[2], k=[3],
        color="#facc15", opacity=0.25, showlegend=False, hoverinfo="skip",
    )

    hover_layer = go.Scatter3d(
        x=hover_x, y=hover_y, z=hover_z, mode="markers",
        marker=dict(size=4, color="rgba(0,0,0,0)"),
        hovertext=hover_text, hoverinfo="text", showlegend=False,
    )

    fig = go.Figure(data=traces + [target_plane, target_plane_2, hover_layer])
    fig.update_layout(
        scene=dict(
            xaxis=dict(title=dimension_col, tickmode="array", tickvals=list(range(n)),
                       ticktext=grouped[dimension_col].astype(str).tolist(),
                       backgroundcolor="#0F172A", gridcolor="#233047"),
            yaxis=dict(title="", showticklabels=False, backgroundcolor="#0F172A", gridcolor="#233047"),
            zaxis=dict(title=metric_col, range=[0, max_val], backgroundcolor="#0F172A", gridcolor="#233047"),
            camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9)),
        ),
        template="plotly_dark", height=520, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig, grouped
