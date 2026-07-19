import pandas as pd
import numpy as np


# =====================================
# NULL VALUES
# =====================================

NULL_VALUES = [
    np.inf,
    -np.inf,

    "",
    " ",
    "  ",

    "None",
    "NONE",
    "none",

    "Null",
    "NULL",
    "null",

    "NaN",
    "NAN",
    "nan",

    "Inf",
    "INF",
    "inf",

    "N/A",
    "n/a",

    "NA",
    "na"
]


# =====================================
# STANDARDIZE NULLS
# =====================================

def standardize_nulls(df):

    temp_df = df.copy()

    temp_df = temp_df.replace(
        NULL_VALUES,
        np.nan
    )

    temp_df = temp_df.replace(
        r"^\s*$",
        np.nan,
        regex=True
    )

    return temp_df


# =====================================
# FILL MISSING VALUES
# =====================================

def fill_missing_values(
    df,
    column,
    method
):

    temp_df = standardize_nulls(df)

    series = temp_df[column]

    # ---------------------------------
    # MODE
    # ---------------------------------

    if method == "Mode":

        mode_val = series.mode()

        fill_value = (
            mode_val.iloc[0]
            if len(mode_val) > 0
            else "Unknown"
        )

        temp_df[column] = (
            series.fillna(fill_value)
        )

        return temp_df

    # ---------------------------------
    # FORWARD FILL
    # ---------------------------------

    if method == "Forward Fill":

        temp_df[column] = (
            series.ffill()
        )

        return temp_df

    # ---------------------------------
    # BACKWARD FILL
    # ---------------------------------

    if method == "Backward Fill":

        temp_df[column] = (
            series.bfill()
        )

        return temp_df

    # ---------------------------------
    # NUMERIC METHODS
    # ---------------------------------

    numeric_col = pd.to_numeric(
        series,
        errors="coerce"
    )

    if numeric_col.notna().sum() == 0:

        mode_val = series.mode()

        fill_value = (
            mode_val.iloc[0]
            if len(mode_val) > 0
            else "Unknown"
        )

        temp_df[column] = (
            series.fillna(fill_value)
        )

        return temp_df

    if method == "Mean":

        fill_value = numeric_col.mean()

    elif method == "Median":

        fill_value = numeric_col.median()

    elif method == "Standard Deviation":

        fill_value = numeric_col.std()

    elif method == "25 Percentile":

        fill_value = numeric_col.quantile(0.25)

    elif method == "50 Percentile":

        fill_value = numeric_col.quantile(0.50)

    elif method == "75 Percentile":

        fill_value = numeric_col.quantile(0.75)

    else:

        fill_value = numeric_col.median()

    if pd.isna(fill_value):

        fill_value = 0

    temp_df[column] = (
        numeric_col.fillna(fill_value)
    )

    return temp_df


# =====================================
# REMOVE DUPLICATES
# =====================================

def remove_duplicates(df):

    return df.drop_duplicates()


# =====================================
# AUTO CLEAN DATASET
# =====================================

def auto_clean_dataset(
    df,
    remove_negative=True
):

    temp_df = standardize_nulls(df)

    numeric_cols = []

    for col in temp_df.columns:

        converted = pd.to_numeric(
            temp_df[col],
            errors="coerce"
        )

        if converted.notna().sum() > (
            len(temp_df) * 0.50
        ):

            temp_df[col] = converted

            numeric_cols.append(col)

    # Numeric columns

    for col in numeric_cols:

        if remove_negative:

            temp_df[col] = (
                temp_df[col].mask(
                    temp_df[col] < 0,
                    np.nan
                )
            )

        median_val = (
            temp_df[col].median()
        )

        if pd.isna(median_val):

            median_val = 0

        temp_df[col] = (
            temp_df[col].fillna(
                median_val
            )
        )

    # Text columns

    for col in temp_df.columns:

        if col not in numeric_cols:

            mode_val = (
                temp_df[col].mode()
            )

            fill_value = (
                mode_val.iloc[0]
                if len(mode_val) > 0
                else "Unknown"
            )

            temp_df[col] = (
                temp_df[col].fillna(
                    fill_value
                )
            )

    temp_df = (
        temp_df.drop_duplicates()
    )

    return temp_df


# =====================================
# DATA QUALITY SCORE
# =====================================

def calculate_quality_score(df):

    temp_df = standardize_nulls(df)

    total_cells = (
        len(temp_df)
        * len(temp_df.columns)
    )

    missing_cells = int(
        temp_df.isna()
        .sum()
        .sum()
    )

    if total_cells == 0:

        return 0

    return round(
        (
            (
                total_cells
                - missing_cells
            )
            / total_cells
        ) * 100,
        2
    )


# =====================================
# AI SUGGESTIONS
# =====================================

def get_ai_cleaning_suggestions(df):

    temp_df = standardize_nulls(df)

    suggestions = []

    missing = (
        temp_df.isna()
        .sum()
    )

    for col in temp_df.columns:

        if missing[col] > 0:

            numeric_col = pd.to_numeric(
                temp_df[col],
                errors="coerce"
            )

            if numeric_col.notna().sum() > (
                len(temp_df) * 0.50
            ):

                method = "Median"

            else:

                method = "Mode"

            suggestions.append(
                f"{col}: {missing[col]} missing values → Recommended: {method}"
            )

    duplicates = (
        temp_df.duplicated()
        .sum()
    )

    if duplicates > 0:

        suggestions.append(
            f"{duplicates} duplicate rows detected"
        )

    if not suggestions:

        suggestions.append(
            "✅ Dataset looks clean."
        )

    return suggestions