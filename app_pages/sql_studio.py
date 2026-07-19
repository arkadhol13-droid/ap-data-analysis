import streamlit as st
import pandas as pd

from services.sql_service import load_dataframe_to_sql


def sql_page(df):

    st.subheader("🗄 Smart SQL Studio")

    conn = load_dataframe_to_sql(df)

    st.success(
        "Dataset Loaded Into SQL Engine"
    )

    st.caption(
        "Table Name = dataset"
    )

    query = st.text_area(
        "SQL Query",
        value="SELECT * FROM dataset LIMIT 10",
        height=150
    )

    if st.button("Run SQL"):

        try:

            result = pd.read_sql_query(
                query,
                conn
            )

            st.success(
                f"{len(result)} rows returned"
            )

            st.dataframe(
                result,
                use_container_width=True
            )

        except Exception as e:

            st.error(str(e))