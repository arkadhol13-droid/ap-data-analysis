import pandas as pd
import plotly.express as px


def generate_chart(
    df,
    x_col,
    y_col,
    chart_type
):

    chart_df = df.copy()

    if y_col in chart_df.columns:

        chart_df[y_col] = pd.to_numeric(
            chart_df[y_col],
            errors="coerce"
        )

    chart_df = chart_df.dropna(
        subset=[x_col]
    )

    # ==========================
    # BAR CHART
    # ==========================

    if chart_type == "Bar Chart":

        chart_df = chart_df.dropna(
            subset=[y_col]
        )

        return px.bar(
            chart_df,
            x=x_col,
            y=y_col
        )

    # ==========================
    # LINE CHART
    # ==========================

    elif chart_type == "Line Chart":

        chart_df = chart_df.dropna(
            subset=[y_col]
        )

        return px.line(
            chart_df,
            x=x_col,
            y=y_col
        )

    # ==========================
    # PIE CHART
    # ==========================

    elif chart_type == "Pie Chart":

        chart_df = chart_df.dropna(
            subset=[y_col]
        )

        return px.pie(
            chart_df,
            names=x_col,
            values=y_col,
            hole=0.3
        )

    # ==========================
    # SCATTER PLOT
    # ==========================

    elif chart_type == "Scatter Plot":

        chart_df = chart_df.dropna(
            subset=[y_col]
        )

        return px.scatter(
            chart_df,
            x=x_col,
            y=y_col
        )

    # ==========================
    # HISTOGRAM
    # ==========================

    elif chart_type == "Histogram":

        return px.histogram(
            chart_df,
            x=x_col
        )

    # ==========================
    # BOX PLOT
    # ==========================

    elif chart_type == "Box Plot":

        chart_df = chart_df.dropna(
            subset=[y_col]
        )

        return px.box(
            chart_df,
            x=x_col,
            y=y_col
        )

    # ==========================
    # TREND LINE
    # ==========================

    elif chart_type == "Trend Line":

        chart_df = chart_df.dropna(
            subset=[y_col]
        )

        return px.scatter(
            chart_df,
            x=x_col,
            y=y_col,
            trendline="ols"
        )

    # ==========================
    # TREEMAP
    # ==========================

    elif chart_type == "Treemap":

        chart_df = chart_df.dropna(
            subset=[y_col]
        )

        return px.treemap(
            chart_df,
            path=[x_col],
            values=y_col
        )

    # ==========================
    # DEFAULT
    # ==========================

    return px.bar(
        chart_df,
        x=x_col,
        y=y_col
    )