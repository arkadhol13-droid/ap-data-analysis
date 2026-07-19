import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

from services.cleaning_service import (
    fill_missing_values,
    auto_clean_dataset,
    remove_duplicates,
    calculate_quality_score,
    get_ai_cleaning_suggestions
)


def cleaning_page(df):

    st.subheader("🛠 Data Cleaning Center")

    # =====================================
    # SESSION STATE
    # =====================================

    if "working_df" not in st.session_state:
        st.session_state.working_df = df.copy()

    if "undo_stack" not in st.session_state:
        st.session_state.undo_stack = []

    if "redo_stack" not in st.session_state:
        st.session_state.redo_stack = []

    working_df = st.session_state.working_df

    # =====================================
    # QUALITY SCORE
    # =====================================

    score = calculate_quality_score(working_df)

    st.metric(
        "📊 Data Quality Score",
        f"{score}%"
    )

    st.divider()

    # =====================================
    # AI RECOMMENDATIONS
    # =====================================

    st.subheader("🤖 AI Recommendations")

    suggestions = get_ai_cleaning_suggestions(
        working_df
    )

    for item in suggestions:
        st.info(item)

    st.divider()

    # =====================================
    # MANUAL CLEANING
    # =====================================

    st.subheader("🧹 Manual Data Cleaning")

    selected_col = st.selectbox(
        "Select Column",
        working_df.columns
    )

    temp_series = (
        working_df[selected_col]
        .replace(
            [
                "", " ",
                "None", "NONE", "none",
                "Null", "NULL", "null",
                "NaN", "NAN", "nan",
                "Inf", "INF", "inf",
                np.inf, -np.inf
            ],
            pd.NA
        )
    )

    missing_count = temp_series.isna().sum()

    st.info(
        f"Missing Values Found: {missing_count}"
    )

    fill_method = st.selectbox(
        "Fill Method",
        [
            "Mean",
            "Median",
            "Mode",
            "Standard Deviation",
            "25 Percentile",
            "50 Percentile",
            "75 Percentile",
            "Forward Fill",
            "Backward Fill"
        ]
    )

    if st.button(
        "✅ Apply In Data",
        use_container_width=True
    ):

        before_missing = temp_series.isna().sum()

        st.session_state.undo_stack.append(
            working_df.copy()
        )

        st.session_state.redo_stack = []

        cleaned_df = fill_missing_values(
            working_df,
            selected_col,
            fill_method
        )

        after_missing = (
            cleaned_df[selected_col]
            .replace(
                [
                    "", " ",
                    "None", "NONE", "none",
                    "Null", "NULL", "null",
                    "NaN", "NAN", "nan",
                    "Inf", "INF", "inf",
                    np.inf, -np.inf
                ],
                pd.NA
            )
            .isna()
            .sum()
        )

        st.session_state.working_df = cleaned_df

        st.success(
            f"{selected_col} cleaned successfully | Before: {before_missing} | After: {after_missing}"
        )

        st.rerun()

    st.divider()

    # =====================================
    # UNDO / REDO
    # =====================================

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "↩ Undo",
            use_container_width=True
        ):

            if st.session_state.undo_stack:

                st.session_state.redo_stack.append(
                    st.session_state.working_df.copy()
                )

                st.session_state.working_df = (
                    st.session_state.undo_stack.pop()
                )

                st.rerun()

    with col2:

        if st.button(
            "↪ Redo",
            use_container_width=True
        ):

            if st.session_state.redo_stack:

                st.session_state.undo_stack.append(
                    st.session_state.working_df.copy()
                )

                st.session_state.working_df = (
                    st.session_state.redo_stack.pop()
                )

                st.rerun()

    st.divider()

    # =====================================
    # REMOVE DUPLICATES
    # =====================================

    if st.button(
        "🗑 Remove Duplicate Rows",
        use_container_width=True
    ):

        before = len(
            st.session_state.working_df
        )

        st.session_state.undo_stack.append(
            st.session_state.working_df.copy()
        )

        st.session_state.redo_stack = []

        st.session_state.working_df = (
            remove_duplicates(
                st.session_state.working_df
            )
        )

        removed = (
            before -
            len(st.session_state.working_df)
        )

        st.success(
            f"{removed} duplicate rows removed"
        )

        st.rerun()

    st.divider()

    # =====================================
    # AI AUTO CLEAN
    # =====================================

    st.subheader("🤖 AI Auto Cleaning")

    remove_negative = st.checkbox(
        "Replace Negative Values",
        value=True
    )

    if st.button(
        "🚀 AI Auto Fix Dataset",
        use_container_width=True
    ):

        st.session_state.undo_stack.append(
            working_df.copy()
        )

        st.session_state.redo_stack = []

        st.session_state.working_df = (
            auto_clean_dataset(
                st.session_state.working_df,
                remove_negative
            )
        )

        st.success(
            "Dataset cleaned successfully"
        )

        st.rerun()

    st.divider()

    # =====================================
    # DATA PREVIEW
    # =====================================

    st.subheader("📊 Final Cleaned Dataset")

    st.dataframe(
        st.session_state.working_df,
        use_container_width=True
    )

    st.subheader("📈 Final Statistics")

    if not st.session_state.working_df.empty:

        st.dataframe(
            st.session_state.working_df
            .describe(include="all")
            .fillna("")
        )

    st.divider()

    # =====================================
    # DOWNLOAD CSV
    # =====================================

    csv = (
        st.session_state.working_df
        .to_csv(index=False)
        .encode("utf-8")
    )

    st.download_button(
        "📥 Download CSV",
        data=csv,
        file_name="cleaned_dataset.csv",
        mime="text/csv",
        use_container_width=True
    )

    # =====================================
    # DOWNLOAD EXCEL
    # =====================================

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter"
    ) as writer:

        st.session_state.working_df.to_excel(
            writer,
            index=False
        )

    st.download_button(
        "📥 Download Excel",
        data=output.getvalue(),
        file_name="cleaned_dataset.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )