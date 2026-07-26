
import pandas as pd

AGG_FUNCS = {
    "Sum": "sum",
    "Average": "mean",
    "Count": "count",
    "Max": "max",
    "Min": "min",
}

MAX_CATEGORICAL_UNIQUE = 200  # above this, a column is treated as free text, not a filterable category


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
