import streamlit as st
from services.chart_service import generate_chart


def chart_page(df):

    st.subheader("📊 Chart Builder")

    if df is None or df.empty:
        st.warning("Please upload a dataset first.")
        return

    col1, col2 = st.columns(2)

    with col1:

        x_col = st.selectbox(
            "📌 X Axis",
            df.columns
        )

    with col2:

        y_col = st.selectbox(
            "📌 Y Axis",
            df.columns
        )

    chart_type = st.selectbox(
        "📈 Select Chart Type",
        [
            "Bar Chart",
            "Line Chart",
            "Pie Chart",
            "Scatter Plot",
            "Histogram",
            "Box Plot",
            "Trend Line",
            "Treemap"
        ]
    )

    st.markdown("### Preview Settings")

    use_container = st.checkbox(
        "Fit Chart to Container",
        value=True
    )

    if st.button(
        "🚀 Generate Chart",
        use_container_width=True
    ):

        try:

            fig = generate_chart(
                df,
                x_col,
                y_col,
                chart_type
            )

            fig.update_layout(
                height=550,
                template="plotly_dark",
                margin=dict(
                    l=20,
                    r=20,
                    t=50,
                    b=20
                )
            )

            st.plotly_chart(
                fig,
                use_container_width=use_container
            )

        except Exception as e:

            st.error(
                f"Chart Error: {e}"
            )

    st.divider()

    st.subheader("📋 Data Preview")

    st.dataframe(
        df.head(20),
        use_container_width=True
    )