import streamlit as st
import pandas as pd
from io import BytesIO

def pivot_page(df):

    st.subheader("📊 Pivot Builder")

    row = st.selectbox(
        "Rows",
        df.columns
    )

    column = st.selectbox(
        "Columns (Optional)",
        ["None"] + list(df.columns)
    )

    value = st.selectbox(
        "Values",
        df.columns
    )

    agg_func = st.selectbox(
        "Aggregation",
        [
            "sum",
            "mean",
            "count",
            "max",
            "min"
        ]
    )

    if st.button("Apply Pivot", use_container_width=True):

        try:

            pivot = pd.pivot_table(
                df,
                index=row,
                columns=None if column == "None" else column,
                values=value,
                aggfunc=agg_func
            )

            st.success("✅ Pivot Created Successfully")

            st.dataframe(
                pivot,
                use_container_width=True
            )

            output = BytesIO()

            with pd.ExcelWriter(
                output,
                engine="xlsxwriter"
            ) as writer:

                pivot.to_excel(
                    writer,
                    sheet_name="Pivot"
                )

            st.download_button(
                label="📥 Download Pivot Excel",
                data=output.getvalue(),
                file_name="pivot.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:

            st.error(
                f"❌ Pivot creation failed: {str(e)}"
            )