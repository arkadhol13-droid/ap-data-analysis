
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

MIN_POINTS_FOR_FORECAST = 4
DEFAULT_FORECAST_PERIODS = 6

# TREND & STATISTICS

def compute_trend(series: pd.Series) -> dict:
    """
    Fits a simple linear trend to a numeric series (index order = time
    order) and returns direction, strength, and % change end-to-end.
    Used as the backbone for both the narrative and the "why is this
    declining" answers.
    """
    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) < 2:
        return {"direction": "flat", "slope": 0.0, "pct_change": 0.0, "volatility": 0.0}

    x = np.arange(len(values))
    slope, intercept = np.polyfit(x, values.values, 1)

    start, end = values.iloc[0], values.iloc[-1]
    pct_change = ((end - start) / abs(start) * 100) if start != 0 else 0.0

    mean = values.mean()
    volatility = (values.std() / abs(mean) * 100) if mean != 0 else 0.0

    if abs(pct_change) < 3:
        direction = "flat"
    elif pct_change > 0:
        direction = "up"
    else:
        direction = "down"

    return {
        "direction": direction,
        "slope": float(slope),
        "pct_change": float(pct_change),
        "volatility": float(volatility),
        "mean": float(mean),
        "start": float(start),
        "end": float(end),
    }


def find_peak_and_trough(df: pd.DataFrame, value_col: str, label_col: str = None) -> dict:
    """
    Locates the best ("achievement") and worst ("downfall") points in a
    numeric column, with the corresponding label (e.g. date, category) if
    one is available, for use in the narrative report.
    """
    series = pd.to_numeric(df[value_col], errors="coerce")
    if series.dropna().empty:
        return {"peak": None, "trough": None}

    peak_idx = series.idxmax()
    trough_idx = series.idxmin()

    def _describe(idx):
        result = {"value": float(series.loc[idx])}
        if label_col and label_col in df.columns:
            label_val = df.loc[idx, label_col]
            if isinstance(label_val, pd.Timestamp):
                result["label"] = label_val.strftime("%d %b %Y")
            else:
                result["label"] = str(label_val)
        return result

    return {"peak": _describe(peak_idx), "trough": _describe(trough_idx)}

# FORECASTING

def forecast_series(df: pd.DataFrame, date_col: str, value_col: str, periods: int = DEFAULT_FORECAST_PERIODS) -> dict:
    """
    Forecasts the next `periods` values of value_col.
    Strategy:
      - >=8 points: Holt's exponential smoothing (captures trend + damping)
      - 4-7 points: simple linear extrapolation
      - <4 points: not enough data, returns method="insufficient_data"
    Never raises -- forecasting is inherently best-effort, so any failure
    falls back to linear extrapolation, and total failure returns a
    graceful "insufficient_data" result rather than crashing the page.
    """
    working = df[[date_col, value_col]].dropna().sort_values(date_col)
    values = pd.to_numeric(working[value_col], errors="coerce").dropna()

    if len(values) < MIN_POINTS_FOR_FORECAST:
        return {"method": "insufficient_data", "forecast": [], "future_labels": []}

    future_labels = _build_future_labels(working[date_col], periods)

    if len(values) >= 8:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            model = ExponentialSmoothing(values.values, trend="add", seasonal=None)
            fit = model.fit()
            forecast_values = fit.forecast(periods)
            return {
                "method": "exponential_smoothing",
                "forecast": [float(v) for v in forecast_values],
                "future_labels": future_labels,
            }
        except Exception:
            pass  # fall through to linear extrapolation

    try:
        x = np.arange(len(values))
        slope, intercept = np.polyfit(x, values.values, 1)
        future_x = np.arange(len(values), len(values) + periods)
        forecast_values = slope * future_x + intercept
        return {
            "method": "linear_trend",
            "forecast": [float(v) for v in forecast_values],
            "future_labels": future_labels,
        }
    except Exception:
        return {"method": "insufficient_data", "forecast": [], "future_labels": []}


def _build_future_labels(date_series: pd.Series, periods: int) -> list:
    """Extends a date axis forward by `periods` steps, inferring the
    typical spacing (daily/weekly/monthly) from the existing data."""
    dates = pd.to_datetime(date_series, errors="coerce").dropna().sort_values()
    if len(dates) < 2:
        return [f"Period {i+1}" for i in range(periods)]

    typical_gap = dates.diff().median()
    last_date = dates.iloc[-1]
    future = [last_date + typical_gap * (i + 1) for i in range(periods)]
    return [d.strftime("%d %b %Y") for d in future]

# NARRATIVE GENERATION (template-based, not an LLM)

def generate_report(df: pd.DataFrame, numeric_cols: list, date_col: str = None) -> dict:
    """
    Builds the full Oracle report: per-metric trend narrative,
    achievements (peaks), downfalls (troughs), and forecasts -- plus a
    ranked set of recommendations. This is what powers the auto-generated
    "what's happening in my data" view on page load, with no user input
    required.
    """
    metrics = []
    recommendations = []

    working = df.sort_values(date_col) if date_col and date_col in df.columns else df

    for col in numeric_cols:
        trend = compute_trend(working[col])
        peak_trough = find_peak_and_trough(working, col, label_col=date_col)
        forecast = (
            forecast_series(working, date_col, col)
            if date_col and date_col in working.columns
            else {"method": "no_date_column", "forecast": [], "future_labels": []}
        )

        narrative = _narrate_metric(col, trend, peak_trough, forecast)

        metrics.append(
            {
                "column": col,
                "trend": trend,
                "peak_trough": peak_trough,
                "forecast": forecast,
                "narrative": narrative,
            }
        )

    recommendations = _generate_recommendations(metrics)

    return {
        "metrics": metrics,
        "recommendations": recommendations,
        "row_count": len(df),
        "has_date_column": bool(date_col),
    }


def _narrate_metric(col: str, trend: dict, peak_trough: dict, forecast: dict) -> str:
    direction_phrase = {
        "up": f"has been trending **upward**, up {abs(trend['pct_change']):.1f}% from start to end",
        "down": f"has been trending **downward**, down {abs(trend['pct_change']):.1f}% from start to end",
        "flat": "has stayed relatively **stable** over this period",
    }[trend["direction"]]

    sentence = f"**{col}** {direction_phrase}."

    if trend.get("volatility", 0) > 40:
        sentence += f" It's also fairly **volatile** (swings of ~{trend['volatility']:.0f}% around the average), which makes single-period numbers less reliable on their own."

    peak = peak_trough.get("peak")
    trough = peak_trough.get("trough")
    if peak:
        label = f" ({peak['label']})" if "label" in peak else ""
        sentence += f" Best point so far: **{peak['value']:,.2f}**{label}."
    if trough:
        label = f" ({trough['label']})" if "label" in trough else ""
        sentence += f" Weakest point: **{trough['value']:,.2f}**{label}."

    if forecast.get("method") not in (None, "insufficient_data", "no_date_column") and forecast.get("forecast"):
        next_val = forecast["forecast"][0]
        last_actual = trend["end"]
        change = ((next_val - last_actual) / abs(last_actual) * 100) if last_actual else 0
        move = "rise" if change > 0 else "fall" if change < 0 else "stay flat"
        sentence += f" Based on the trend so far, the next period is projected to **{move}** to roughly **{next_val:,.2f}**."

    return sentence


def _generate_recommendations(metrics: list) -> list:
    """
    Ranks metrics by how much attention they deserve, using simple,
    explainable rules -- not a black box. Declining + high-volatility
    metrics surface first (biggest risk), then strong performers
    (double-down opportunities).
    """
    recs = []

    declining = [m for m in metrics if m["trend"]["direction"] == "down"]
    declining.sort(key=lambda m: m["trend"]["pct_change"])  # most negative first
    for m in declining[:3]:
        recs.append(
            {
                "priority": "high",
                "text": f"⚠️ **{m['column']}** is down {abs(m['trend']['pct_change']):.1f}% — "
                f"investigate what changed around the weakest point "
                f"({m['peak_trough']['trough'].get('label', 'the low period') if m['peak_trough']['trough'] else 'the low period'}) "
                f"before it drags down related metrics.",
            }
        )

    growing = [m for m in metrics if m["trend"]["direction"] == "up"]
    growing.sort(key=lambda m: -m["trend"]["pct_change"])
    for m in growing[:2]:
        recs.append(
            {
                "priority": "opportunity",
                "text": f"📈 **{m['column']}** is up {m['trend']['pct_change']:.1f}% — "
                f"this is working. Consider what's driving it and whether it can be applied elsewhere.",
            }
        )

    volatile = [m for m in metrics if m["trend"].get("volatility", 0) > 50]
    for m in volatile[:2]:
        recs.append(
            {
                "priority": "medium",
                "text": f"🎯 **{m['column']}** is highly volatile — inconsistent results make this "
                f"a good candidate for standardizing the process behind it.",
            }
        )

    if not recs:
        recs.append({"priority": "info", "text": "Your metrics look broadly stable — no major red flags detected."})

    return recs

# Q&A ENGINE (rule-based natural-language pattern matching)


AGG_KEYWORDS = {
    "highest": "max", "maximum": "max", "top": "max", "best": "max", "peak": "max",
    "lowest": "min", "minimum": "min", "worst": "min", "bottom": "min",
    "average": "mean", "mean": "mean", "avg": "mean",
    "total": "sum", "sum": "sum",
    "count": "count", "how many": "count",
}

RANK_DIRECTION_KEYWORDS = {
    "highest": False, "maximum": False, "top": False, "best": False, "most": False,
    "lowest": True, "minimum": True, "bottom": True, "worst": True, "least": True,
}


def _find_columns_in_text(text: str, columns: list) -> list:
    """Returns every column name mentioned in `text`, matched on whole
    words/phrases (case-insensitive, underscores treated as spaces),
    longest names checked first so e.g. 'monthly_income' beats 'income'."""
    import re

    text_norm = " " + text.lower().replace("_", " ") + " "
    matches = []
    for col in sorted(columns, key=lambda c: -len(c)):
        col_norm = col.lower().replace("_", " ").replace("-", " ").strip()
        if not col_norm:
            continue
        pattern = r"(?<!\w)" + re.escape(col_norm) + r"(?!\w)"
        if re.search(pattern, text_norm):
            matches.append(col)
    return matches


def rank_by_dimension(df: pd.DataFrame, dimension_col: str, metric_col: str, ascending: bool = False, top_n: int = 5) -> pd.DataFrame:
    """The structural core of 'which X has the highest/lowest Y': group the
    categorical dimension, sum the numeric metric, sort, return the ranking.
    This is what makes the app sector-agnostic -- it never needs to know
    what 'City' or 'Department' or 'Hospital Ward' means, only that one
    column is a category and the other is a number."""
    working = df[[dimension_col, metric_col]].copy()
    working[metric_col] = pd.to_numeric(working[metric_col], errors="coerce")
    grouped = (
        working.dropna(subset=[metric_col])
        .groupby(dimension_col, dropna=False)[metric_col]
        .sum()
        .reset_index()
        .sort_values(metric_col, ascending=ascending)
    )
    return grouped.head(top_n)


def answer_universal_question(df: pd.DataFrame, question: str, col_types: dict) -> str:
    """
    Sector-agnostic Q&A: detects whichever columns are actually mentioned
    in the question and classifies each as a dimension (categorical) or
    metric (numeric) using col_types (from bi_service.detect_column_types)
    -- no hard-coded column names or question templates, so this works the
    same way for Sales, Telecom, HR, Healthcare, or any other structured
    dataset. Falls back to plain per-column stats when only one column is
    mentioned, and to a generic "ask me about a column" hint when none is.
    """
    q = question.lower().strip()
    all_cols = list(col_types.keys())
    mentioned = _find_columns_in_text(q, all_cols)

    dimensions = [c for c in mentioned if col_types.get(c) == "categorical"]
    metrics = [c for c in mentioned if col_types.get(c) == "numeric"]

    # --- CURRENT -> GAP -> TARGET: "target 85" mentioned alongside a metric
    import re
    target_match = re.search(r"target\s*(?:of|is|=)?\s*([\d,]+\.?\d*)", q)
    if target_match and metrics:
        target_value = float(target_match.group(1).replace(",", ""))
        metric = metrics[0]
        series = pd.to_numeric(df[metric], errors="coerce").dropna()
        if not series.empty:
            current = float(series.iloc[-1]) if len(series) > 1 else float(series.mean())
            gap = target_value - current
            improvement_pct = (gap / current * 100) if current else None
            direction = "increase" if gap > 0 else "decrease" if gap < 0 else "no change"
            lines = [
                f"**Current → Gap → Target for {metric}:**",
                f"- Current: **{current:,.2f}**",
                f"- Target: **{target_value:,.2f}**",
                f"- Gap: **{abs(gap):,.2f}** ({direction} needed)",
            ]
            if improvement_pct is not None:
                lines.append(f"- Required change: **{abs(improvement_pct):.1f}%**")
            return "\n".join(lines)

    # --- DIMENSION + METRIC RANKING: "which city has highest sales" ---
    if dimensions and metrics:
        dimension_col, metric_col = dimensions[0], metrics[0]
        ascending = any(k in q for k, asc in RANK_DIRECTION_KEYWORDS.items() if asc and k in q)
        ranking = rank_by_dimension(df, dimension_col, metric_col, ascending=ascending, top_n=5)
        if ranking.empty:
            return f"No usable data to rank **{dimension_col}** by **{metric_col}**."
        top_row = ranking.iloc[0]
        direction_word = "lowest" if ascending else "highest"
        lines = [
            f"**{top_row[dimension_col]}** has the {direction_word} total **{metric_col}**: "
            f"**{top_row[metric_col]:,.2f}**.",
            "",
            f"Top {len(ranking)} {dimension_col} by {metric_col}:",
        ]
        for _, row in ranking.iterrows():
            lines.append(f"- {row[dimension_col]}: {row[metric_col]:,.2f}")
        return "\n".join(lines)

    # --- Dimension mentioned but no metric: rank by row count instead 
    if dimensions and not metrics:
        dimension_col = dimensions[0]
        counts = df[dimension_col].value_counts().head(5)
        lines = [f"Breakdown of **{dimension_col}**:"]
        for name, count in counts.items():
            lines.append(f"- {name}: {count} records")
        return "\n".join(lines)

    # --- Metric only, no dimension: fall back to the numeric-only engine 
    if metrics:
        return None  # signal caller to use answer_question() for numeric-only handling

    return None  # no columns recognized at all

# PAST / PRESENT / FUTURE FRAMING

def generate_past_present_future(df: pd.DataFrame, metric_col: str, date_col: str = None) -> dict:
    """
    Restructures the same trend/forecast computations already used
    elsewhere in this module into an explicit Past / Present / Future
    narrative, per the requested framing. Predictions are always phrased
    as projections, never guarantees, and Future is omitted entirely
    when there isn't enough historical data to forecast responsibly.
    """
    working = df.sort_values(date_col) if date_col and date_col in df.columns else df
    trend = compute_trend(working[metric_col])
    peak_trough = find_peak_and_trough(working, metric_col, label_col=date_col)

    past_lines = []
    if trend["direction"] == "up":
        past_lines.append(f"**{metric_col}** grew {abs(trend['pct_change']):.1f}% from the start of this data to the middle/recent period.")
    elif trend["direction"] == "down":
        past_lines.append(f"**{metric_col}** declined {abs(trend['pct_change']):.1f}% over the period covered by this data.")
    else:
        past_lines.append(f"**{metric_col}** stayed relatively flat historically.")
    if peak_trough.get("peak"):
        label = f" ({peak_trough['peak']['label']})" if "label" in peak_trough["peak"] else ""
        past_lines.append(f"Historical high: **{peak_trough['peak']['value']:,.2f}**{label}.")

    present_lines = [f"Current average is **{trend['mean']:,.2f}**, most recent value is **{trend['end']:,.2f}**."]
    if trend.get("volatility", 0) > 40:
        present_lines.append(f"Results are currently **volatile** (~{trend['volatility']:.0f}% swing around average) — treat single-period numbers with caution.")
    if peak_trough.get("trough"):
        label = f" ({peak_trough['trough']['label']})" if "label" in peak_trough["trough"] else ""
        present_lines.append(f"Weakest point on record: **{peak_trough['trough']['value']:,.2f}**{label}.")

    future_lines = []
    forecast = None
    if date_col and date_col in working.columns:
        forecast = forecast_series(working, date_col, metric_col)
        if forecast["method"] != "insufficient_data" and forecast.get("forecast"):
            next_val = forecast["forecast"][0]
            change = ((next_val - trend["end"]) / abs(trend["end"]) * 100) if trend["end"] else 0
            move = "rise toward" if change > 0 else "fall toward" if change < 0 else "stay near"
            future_lines.append(
                f"If the current trend continues, {metric_col} is projected to {move} "
                f"**{next_val:,.2f}** next period. This is a projection based on past data, not a guarantee."
            )
        else:
            future_lines.append("Not enough historical data points yet to generate a reliable forecast.")
    else:
        future_lines.append("Add a date/time column to this dataset to unlock future projections.")

    return {
        "past": " ".join(past_lines),
        "present": " ".join(present_lines),
        "future": " ".join(future_lines),
        "forecast": forecast,
    }


def answer_question(df: pd.DataFrame, question: str, numeric_cols: list, date_col: str = None) -> str:
    """
    Rule-based Q&A: matches the question against known patterns (highest/
    lowest/average/total X, trend of X, why is X declining, what should I
    improve, forecast X) and answers using the same statistics that power
    the report above. This is not an LLM -- it recognizes patterns, not
    open-ended language -- but it covers the core questions people
    actually ask a dashboard.
    """
    q = question.lower().strip()
    if not q:
        return "Ask me something about your data — try \"highest sales\", \"why is X declining\", or \"forecast revenue\"."

    matched_col = _match_column(q, numeric_cols)

    # "what should I improve" / "where should I focus"
    if any(p in q for p in ["improve", "focus", "should i", "recommend", "what's wrong", "whats wrong"]):
        if date_col:
            report = generate_report(df, numeric_cols, date_col)
        else:
            report = generate_report(df, numeric_cols, None)
        recs = report["recommendations"]
        return "\n\n".join(f"- {r['text']}" for r in recs[:3])

    # "why is X declining/bad/down"
    if any(p in q for p in ["why", "declining", "bad", "down", "dropping", "worse"]) and matched_col:
        trend = compute_trend(df[matched_col])
        pt = find_peak_and_trough(df, matched_col, label_col=date_col)
        return _narrate_metric(matched_col, trend, pt, {"method": "no_date_column", "forecast": []})

    # "forecast/predict X" / "future of X"
    if any(p in q for p in ["forecast", "predict", "future", "next month", "next quarter", "will be"]) and matched_col and date_col:
        forecast = forecast_series(df, date_col, matched_col)
        if forecast["method"] == "insufficient_data":
            return f"Not enough historical data points for **{matched_col}** yet to forecast reliably (need at least {MIN_POINTS_FOR_FORECAST})."
        lines = [f"**Forecast for {matched_col}** (method: {forecast['method'].replace('_', ' ')}):"]
        for label, val in zip(forecast["future_labels"], forecast["forecast"]):
            lines.append(f"- {label}: **{val:,.2f}**")
        return "\n".join(lines)

    # aggregation questions: highest/lowest/average/total X
    for keyword, func in AGG_KEYWORDS.items():
        if keyword in q:
            col = matched_col or (numeric_cols[0] if numeric_cols else None)
            if not col:
                return "I couldn't find a numeric column to answer that — try naming a column from your dataset."
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                return f"No usable numeric data found in **{col}**."
            value = series.count() if func == "count" else getattr(series, func)()
            return f"The **{keyword}** {col} is **{value:,.2f}**." if func != "count" else f"There are **{int(value)}** records."

    # trend / how is X doing
    if matched_col and any(p in q for p in ["trend", "how is", "how's", "doing", "performing"]):
        trend = compute_trend(df[matched_col])
        pt = find_peak_and_trough(df, matched_col, label_col=date_col)
        return _narrate_metric(matched_col, trend, pt, {"method": "no_date_column", "forecast": []})

    if matched_col:
        trend = compute_trend(df[matched_col])
        return f"**{matched_col}** — current average is **{trend['mean']:,.2f}**, trend is **{trend['direction']}**. Try asking \"why is {matched_col} declining\" or \"forecast {matched_col}\" for more detail."

    return (
        "I'm not sure which column you mean. Available numeric columns: "
        + ", ".join(f"`{c}`" for c in numeric_cols[:10])
        + ". Try: \"highest <column>\", \"why is <column> declining\", \"forecast <column>\", or \"what should I improve\"."
    )


def _match_column(question: str, numeric_cols: list) -> str:
    """Finds the first numeric column name (case-insensitive, underscores
    treated as spaces) mentioned in the question."""
    q_normalized = question.replace("_", " ")
    for col in numeric_cols:
        col_normalized = col.replace("_", " ").lower()
        if col_normalized in q_normalized:
            return col
    return None


def answer_any_question(df: pd.DataFrame, question: str, col_types: dict, numeric_cols: list, date_col: str = None) -> str:
    """
    The single entry point the UI should call. Tries the sector-agnostic
    dimension+metric engine first (handles "which X has highest Y" and
    "current vs target" style questions for ANY dataset); falls back to
    the numeric-only engine (highest/lowest/average/forecast/trend/
    recommendations on a single named column) when no categorical
    dimension is involved.
    """
    universal_answer = answer_universal_question(df, question, col_types)
    if universal_answer is not None:
        return universal_answer
    return answer_question(df, question, numeric_cols, date_col)
