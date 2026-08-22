
import pandas as pd

from services.oracle_service import compute_trend

SIGNIFICANCE_THRESHOLD_PCT = 5.0

HIGH_PRIORITY_PCT = 15.0
MEDIUM_PRIORITY_PCT = 8.0

MAX_DRILL_LEVELS = 3
MIN_ROWS_TO_KEEP_DRILLING = 4


def _period_split_totals(df: pd.DataFrame, dimension_col: str, metric_col: str, date_col: str = None):
    """Splits the data into an earlier half and a later half (time-ordered
    if a date column is available) and returns each half's per-category
    totals -- the building block for measuring how much each category's
    contribution changed."""
    working = df.sort_values(date_col) if date_col and date_col in df.columns else df
    working = working[[dimension_col, metric_col]].copy()
    working[metric_col] = pd.to_numeric(working[metric_col], errors="coerce")
    working = working.dropna(subset=[metric_col])

    half = len(working) // 2
    if half == 0:
        return None, None

    first_totals = working.iloc[:half].groupby(dimension_col, dropna=False)[metric_col].sum()
    second_totals = working.iloc[half:].groupby(dimension_col, dropna=False)[metric_col].sum()
    return first_totals, second_totals


def drill_down_contributors(df: pd.DataFrame, dimension_col: str, metric_col: str, date_col: str = None, top_n: int = 3) -> list:
    """
    Finds which categories in `dimension_col` moved the most (up or down)
    between the first and second half of the data for `metric_col`.
    Returns a list of {category, before, after, change, pct_change},
    sorted with the biggest decline first.
    """
    first_totals, second_totals = _period_split_totals(df, dimension_col, metric_col, date_col)
    if first_totals is None:
        return []

    all_categories = set(first_totals.index) | set(second_totals.index)
    results = []
    for category in all_categories:
        before = float(first_totals.get(category, 0) or 0)
        after = float(second_totals.get(category, 0) or 0)
        change = after - before
        pct_change = (change / abs(before) * 100) if before else None
        results.append({"category": category, "before": before, "after": after, "change": change, "pct_change": pct_change})

    results.sort(key=lambda r: r["change"])
    return results[:top_n]


def cascading_drill_down(df: pd.DataFrame, dimension_cols: list, metric_col: str, date_col: str = None, declining: bool = True) -> list:
    """
    Automatic multi-level drill-down: at each level, checks every
    remaining categorical dimension, finds whichever one has a category
    with the single biggest movement (decline or growth, matching the
    overall direction), locks that category in, filters the data down to
    just that slice, and repeats with the remaining dimensions. This
    produces chains like Region -> City -> Product using whatever
    dimensions the dataset actually has -- nothing is hard-coded to a
    specific sector's column names.
    """
    path = []
    subset = df
    remaining_dims = list(dimension_cols)

    for _ in range(min(MAX_DRILL_LEVELS, len(remaining_dims))):
        best_dim, best_contributor, best_magnitude = None, None, 0

        for dim in remaining_dims:
            if subset[dim].nunique(dropna=True) < 2:
                continue  # only one category present -- nothing to drill into
            contributors = drill_down_contributors(subset, dim, metric_col, date_col, top_n=1)
            if not contributors:
                continue
            candidate = contributors[0]

            magnitude = -candidate["change"] if declining else candidate["change"]
            if magnitude > best_magnitude:
                best_dim, best_contributor, best_magnitude = dim, candidate, magnitude

        if not best_dim or not best_contributor or best_magnitude <= 0:
            break

        path.append(
            {
                "dimension": best_dim,
                "category": best_contributor["category"],
                "change": best_contributor["change"],
                "pct_change": best_contributor["pct_change"],
            }
        )

        subset = subset[subset[best_dim] == best_contributor["category"]]
        remaining_dims = [d for d in remaining_dims if d != best_dim]

        if len(subset) < MIN_ROWS_TO_KEEP_DRILLING:
            break

    return path


def detect_business_problems(df: pd.DataFrame, col_types: dict, date_col: str = None, metrics: list = None) -> list:
    """
    Main entry point. Scans every selected numeric metric for a
    significant overall trend; for each one that clears the threshold,
    cascades through the dataset's categorical dimensions to find where
    the movement is concentrated, and packages the result as a ranked
    finding (priority + everything needed to render Problem -> Evidence
    -> Impact -> Action -> Target).
    """
    numeric_cols = metrics or [c for c, t in col_types.items() if t == "numeric"]
    dimension_cols = [c for c, t in col_types.items() if t == "categorical"]

    findings = []

    for metric in numeric_cols:
        if date_col and date_col in df.columns:
            daily_totals = df.groupby(date_col)[metric].apply(lambda s: pd.to_numeric(s, errors="coerce").sum()).sort_index()
            trend = compute_trend(daily_totals)
        else:
            trend = compute_trend(df[metric])

        if abs(trend["pct_change"]) < SIGNIFICANCE_THRESHOLD_PCT:
            continue

        is_decline = trend["direction"] == "down"

        drill_path = []
        if dimension_cols:
            drill_path = cascading_drill_down(df, dimension_cols, metric, date_col, declining=is_decline)

        findings.append(
            {
                "metric": metric,
                "is_decline": is_decline,
                "overall_pct_change": trend["pct_change"],
                "start_value": trend["start"],
                "end_value": trend["end"],
                "impact_value": abs(trend["end"] - trend["start"]),
                "drill_path": drill_path,
            }
        )

    for finding in findings:
        overall_magnitude = abs(finding["overall_pct_change"])
        drill_magnitude = 0.0
        if finding["drill_path"]:
            deepest_step = finding["drill_path"][-1]
            if deepest_step["pct_change"] is not None:
                drill_magnitude = abs(deepest_step["pct_change"])

        magnitude = max(overall_magnitude, drill_magnitude)
        finding["_priority_magnitude"] = magnitude

        if magnitude >= HIGH_PRIORITY_PCT:
            finding["priority"] = "high"
        elif magnitude >= MEDIUM_PRIORITY_PCT:
            finding["priority"] = "medium"
        else:
            finding["priority"] = "low"

    findings.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2}[f["priority"]], -f["_priority_magnitude"]))
    for f in findings:
        f.pop("_priority_magnitude", None)

    return findings


def format_finding_markdown(finding: dict) -> str:
    """Renders one finding as the requested What/Where/Why/Impact/Action/
    Target block, in plain business language."""
    metric = finding["metric"]
    is_decline = finding["is_decline"]
    direction_word = "declined" if is_decline else "grown"
    priority_badge = {"high": "🔴 HIGH PRIORITY", "medium": "🟠 MEDIUM PRIORITY", "low": "🟡 LOW PRIORITY"}[finding["priority"]]

    lines = [f"{priority_badge}", f"**🚨 What:** {metric} has {direction_word} **{abs(finding['overall_pct_change']):.1f}%** overall."]

    drill_path = finding["drill_path"]
    if drill_path:
        chain_text = " → ".join(
            f"{step['category']} ({step['dimension']}, {step['pct_change']:+.1f}%)" if step["pct_change"] is not None
            else f"{step['category']} ({step['dimension']})"
            for step in drill_path
        )
        lines.append(f"**📍 Where:** Most concentrated in {chain_text}.")

        last_category = drill_path[-1]["category"]
        lines.append(
            f"**🔎 Why (contributing factor, not a confirmed cause):** {last_category} shows the largest "
            f"measurable movement within this breakdown — the data points here first, but this identifies "
            f"*where* the change concentrates, not a proven root cause."
        )
        focus_target = last_category
    else:
        lines.append("**📍 Where:** No categorical breakdown available to localize this further.")
        focus_target = metric

    lines.append(f"**💰 Impact:** {metric} moved by **{finding['impact_value']:,.2f}** (absolute) over the period covered by this data.")

    if is_decline:
        lines.append(f"**🎯 Recommended action:** Investigate **{focus_target}** first — it accounts for the largest share of this decline.")
        lines.append(f"**📈 Target:** Recover **{metric}** toward its earlier level of **{finding['start_value']:,.2f}**.")
    else:
        lines.append(f"**🎯 Recommended action:** Identify what's driving improvement in **{focus_target}** and consider applying it elsewhere.")
        lines.append(f"**📈 Target:** Sustain the current trend — current level is **{finding['end_value']:,.2f}**.")

    return "\n\n".join(lines)
