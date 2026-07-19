import re
import streamlit as st
import pandas as pd
import numpy as np


# ----------------------------------------------------------------------
# Helper: safely pull the CLEANED dataframe.
#
# If your Data Cleaning page saves the cleaned df somewhere in
# st.session_state, this will find it automatically by checking a list
# of common key names. If you know your exact key name, just add it to
# CLEANED_DF_KEYS below (put it first for priority).
# ----------------------------------------------------------------------
CLEANED_DF_KEYS = [
    "cleaned_df",
    "clean_df",
    "df_cleaned",
    "cleaned_data",
    "clean_data",
    "final_df",
    "df",
    "data",
]


def get_cleaned_df(fallback_df):
    """
    Returns the cleaned dataframe from session_state if available,
    otherwise falls back to whatever df was passed into ai_page().
    """
    for key in CLEANED_DF_KEYS:
        if key in st.session_state:
            candidate = st.session_state[key]
            if isinstance(candidate, pd.DataFrame) and not candidate.empty:
                return candidate

    return fallback_df


def safe_to_numeric(series, clip_outliers=True, outlier_z=6):
    """
    Robust numeric conversion for messy real-world columns.

    Fixes the "inf" bug at THREE layers:

    1. TEXT LEVEL: pandas' to_numeric will happily parse the literal
       text "inf" / "infinity" / "-inf" as REAL infinity, not as a
       missing value. So we explicitly blank out any such tokens
       (case-insensitive) before conversion.
    2. POST-CONVERSION: any +inf / -inf that still slips through
       (e.g. was already stored as a float inf in the dataframe) gets
       replaced with NaN.
    3. OVERFLOW / CORRUPT-DATA GUARD: if the "cleaned" data has a few
       insanely large corrupt values (e.g. a stray 1e300 from a bad
       fillna/calculation upstream), sum()/mean() can silently overflow
       to inf even with no literal inf values. We optionally drop values
       that are extreme outliers (z-score based) before aggregating.
    """

    # Layer 1: neutralize text tokens that mean "not a real number"
    bad_tokens = r"(?i)^\s*(inf|-inf|\+inf|infinity|-infinity|nan|none|null|na|n/a)\s*$"

    cleaned = (
        series.astype(str)
        .str.replace(r"[₹$,%\s]", "", regex=True)
    )
    cleaned = cleaned.mask(cleaned.str.match(bad_tokens, na=False), np.nan)

    numeric = pd.to_numeric(cleaned, errors="coerce")

    # Layer 2: kill any inf / -inf so they never leak into aggregations
    numeric = numeric.replace([np.inf, -np.inf], np.nan)

    # Layer 3: guard against overflow from extreme corrupt values
    if clip_outliers and numeric.notna().sum() > 1:
        mean = numeric.mean()
        std = numeric.std()
        if std and std > 0 and np.isfinite(mean) and np.isfinite(std):
            z_scores = (numeric - mean).abs() / std
            numeric = numeric.where(z_scores <= outlier_z, np.nan)

    return numeric


def find_matched_column(q, df):
    """
    Finds the best matching column for a natural language query.
    Uses WORD-BOUNDARY regex matching (not plain substring "in" checks),
    so "age" won't wrongly match inside "average". Longest / most specific
    column names are checked first.
    """

    cleaned_cols = []
    for col in df.columns:
        clean_col = (
            col.lower()
            .replace("_", " ")
            .replace("-", " ")
            .strip()
        )
        cleaned_cols.append((clean_col, col))

    cleaned_cols.sort(key=lambda x: len(x[0]), reverse=True)

    # 1) Exact whole-phrase match
    for clean_col, original_col in cleaned_cols:
        pattern = r"\b" + re.escape(clean_col) + r"\b"
        if re.search(pattern, q):
            return original_col

    # 2) Partial whole-word match
    q_words = set(re.findall(r"\b\w+\b", q))
    for clean_col, original_col in cleaned_cols:
        col_words = clean_col.split()
        if any(word in q_words for word in col_words):
            return original_col

    return None


def ai_page(df):

    st.subheader("💬 Ask Your Data")

    # Always operate on the CLEANED dataset, not the raw upload
    df = get_cleaned_df(df)

    st.info("""
    Examples:
    • Highest Sales
    • Lowest Profit
    • Average Revenue
    • Total Amount
    • Count Product
    • Missing Values
    • Total Rows
    • Total Columns
    • Top Category
    """)

    question = st.text_input(
        "Ask anything about your cleaned dataset"
    )

    if not question:
        return

    q = question.lower()

    matched_col = find_matched_column(q, df)

    # Highest

    if "highest" in q or "maximum" in q:

        if matched_col:

            numeric_col = safe_to_numeric(df[matched_col])
            value = numeric_col.max()
            row = df[numeric_col == value]

            st.success(f"Highest {matched_col}: {value}")
            st.dataframe(row, use_container_width=True)
        else:
            st.warning("Couldn't find a matching column for your question.")

        return

    # Lowest

    if "lowest" in q or "minimum" in q:

        if matched_col:

            numeric_col = safe_to_numeric(df[matched_col])
            value = numeric_col.min()
            row = df[numeric_col == value]

            st.success(f"Lowest {matched_col}: {value}")
            st.dataframe(row, use_container_width=True)
        else:
            st.warning("Couldn't find a matching column for your question.")

        return

    # Average

    if "average" in q or "mean" in q:

        if matched_col:

            value = safe_to_numeric(df[matched_col]).mean()

            if pd.isna(value) or not np.isfinite(value):
                st.warning(
                    f"'{matched_col}' has no valid numeric values to average."
                )
                with st.expander("🔍 Debug: raw values in this column"):
                    st.write(df[matched_col].head(20))
                    st.write("Dtype:", df[matched_col].dtype)
            else:
                st.success(f"Average {matched_col}: {value:.2f}")
        else:
            st.warning("Couldn't find a matching column for your question.")

        return

    # Median

    if "median" in q:

        if matched_col:

            value = safe_to_numeric(df[matched_col]).median()

            if pd.isna(value):
                st.warning(
                    f"'{matched_col}' has no valid numeric values for median."
                )
            else:
                st.success(f"Median {matched_col}: {value:.2f}")
        else:
            st.warning("Couldn't find a matching column for your question.")

        return

    # Sum / Total

    if "sum" in q or "total" in q:

        if matched_col:

            value = safe_to_numeric(df[matched_col]).sum()
            st.success(f"Total {matched_col}: {value:,.2f}")
        else:
            st.warning("Couldn't find a matching column for your question.")

        return

    # Count

    if "count" in q:

        if matched_col:

            value = df[matched_col].count()
            st.success(f"Count of {matched_col}: {value}")
        else:
            st.warning("Couldn't find a matching column for your question.")

        return

    # Top Category

    if "top" in q:

        if matched_col:

            value = (
                df[matched_col]
                .astype(str)
                .value_counts()
                .idxmax()
            )
            st.success(f"Top {matched_col}: {value}")
        else:
            st.warning("Couldn't find a matching column for your question.")

        return

    # Missing Values

    if "missing" in q or "null" in q:

        missing = df.isna().sum().reset_index()
        missing.columns = ["Column", "Missing Values"]
        st.dataframe(missing, use_container_width=True)

        return

    # Rows

    if "rows" in q:

        st.success(f"Total Rows: {len(df)}")
        return

    # Columns

    if "columns" in q:

        st.success(f"Total Columns: {len(df.columns)}")
        return

    # Dataset Shape

    if "shape" in q:

        st.success(f"Dataset Shape: {df.shape}")
        return

    # Describe Dataset

    if "summary" in q or "describe" in q:

        st.dataframe(df.describe(include="all"), use_container_width=True)
        return

    st.warning(
        "Query not understood. Try: Highest Sales, Average Revenue, Total Amount, Missing Values, Dataset Summary"
    )