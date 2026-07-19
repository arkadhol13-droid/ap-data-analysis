import streamlit as st
import pandas as pd
from io import BytesIO


def dashboard_page(df):

    st.success("✅ File Uploaded Successfully")

    # =====================================
    # PREVIEW
    # =====================================

    with st.expander("🔍 Preview Data"):

        st.dataframe(
            df.head(20),
            use_container_width=True
        )

    st.divider()

    # =====================================
    # DATASET OVERVIEW
    # =====================================

    st.subheader("📈 Dataset Overview")

    st.write(
        f"Dataset Shape: {df.shape}"
    )

    total_cells = (
        df.shape[0] *
        df.shape[1]
    )

    missing_cells = int(
        df.isna().sum().sum()
    )

    quality = (
        (
            total_cells -
            missing_cells
        ) / total_cells * 100
        if total_cells > 0
        else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.markdown(f"""
        <div class="stat-card">
            <h3>📄 Total Rows</h3>
            <h2>{df.shape[0]}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col2:

        st.markdown(f"""
        <div class="stat-card">
            <h3>📊 Total Columns</h3>
            <h2>{df.shape[1]}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col3:

        st.markdown(f"""
        <div class="stat-card">
            <h3>⚠ Missing Values</h3>
            <h2>{missing_cells}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col4:

        st.markdown(f"""
        <div class="stat-card">
            <h3>✅ Quality Score</h3>
            <h2>{quality:.1f}%</h2>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # =====================================
    # DATASET STATISTICS
    # =====================================

    st.subheader("📊 Dataset Statistics")

    if not df.empty:

        st.dataframe(
            df.describe(
                include="all"
            ).fillna(""),
            use_container_width=True
        )

    else:

        st.warning(
            "Dataset is empty."
        )

    st.divider()

    # =====================================
    # FILTERS
    # =====================================

    st.subheader("🔎 Filters")

    filter_col = st.selectbox(
        "Select Filter Column",
        ["None"] + list(df.columns)
    )

    filtered_df = df.copy()

    if filter_col != "None":

        unique_values = (
            df[filter_col]
            .dropna()
            .unique()
        )

        selected_values = st.multiselect(
            "Select Values",
            unique_values,
            default=unique_values
        )

        filtered_df = df[
            df[filter_col]
            .isin(selected_values)
        ]

    st.write("Filtered Data")

    st.dataframe(
        filtered_df,
        use_container_width=True
    )

    st.divider()

    # =====================================
    # QUICK INSIGHTS
    # =====================================

    st.subheader("📈 Quick Insights")

    insight_col1, insight_col2 = st.columns(2)

    with insight_col1:

        st.info(
            f"Rows: {len(filtered_df)}"
        )

    with insight_col2:

        st.info(
            f"Columns: {len(filtered_df.columns)}"
        )

    numeric_cols = (
        filtered_df
        .select_dtypes(
            include="number"
        )
        .columns
    )

    if len(numeric_cols) > 0:

        st.write(
            "Numeric Summary"
        )

        st.dataframe(
            filtered_df[
                numeric_cols
            ].describe(),
            use_container_width=True
        )

    missing = (
        filtered_df
        .isnull()
        .sum()
        .reset_index()
    )

    missing.columns = [
        "Column",
        "Missing Values"
    ]

    st.write(
        "Missing Values Analysis"
    )

    st.dataframe(
        missing,
        use_container_width=True
    )

    st.divider()

    # =====================================
    # DOWNLOAD SUMMARY
    # =====================================

    st.subheader(
        "⬇ Download Summary"
    )

    summary = (
        filtered_df
        .describe(
            include="all"
        )
        .fillna("")
    )

    excel = BytesIO()

    with pd.ExcelWriter(
        excel,
        engine="xlsxwriter"
    ) as writer:

        summary.to_excel(
            writer,
            sheet_name="Summary"
        )

    st.download_button(
        "📥 Download Summary Excel",
        data=excel.getvalue(),
        file_name="summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
