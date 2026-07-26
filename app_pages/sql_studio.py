import streamlit as st
import pandas as pd

from services.sql_service import load_dataframe_to_sql
from security.validators import is_safe_sql_select

MAX_RESULT_ROWS = 5000


def sql_page(df):

    st.subheader("🗄 Smart SQL Studio")

    conn = load_dataframe_to_sql(df)

    st.success("Dataset Loaded Into SQL Engine")
    st.caption("Table Name = dataset — read-only: SELECT queries only.")

    query = st.text_area(
        "SQL Query",
        value="SELECT * FROM dataset LIMIT 10",
        height=150,
    )

    if st.button("Run SQL"):

        is_valid, error_message = is_safe_sql_select(query)

        if not is_valid:
            st.error(f"Query rejected: {error_message}")
        else:
            try:
                result = pd.read_sql_query(query, conn)

                if len(result) > MAX_RESULT_ROWS:
                    st.warning(
                        f"Result truncated to the first {MAX_RESULT_ROWS} rows "
                        f"(query returned {len(result)})."
                    )
                    result = result.head(MAX_RESULT_ROWS)

                st.success(f"{len(result)} rows returned")

                st.dataframe(
                    result,
                    use_container_width=True,
                )
            except Exception:
                st.error(
                    "Query failed. Please check your SQL syntax and that "
                    "referenced columns exist in the 'dataset' table."
                )