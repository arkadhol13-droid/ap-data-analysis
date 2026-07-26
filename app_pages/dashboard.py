import uuid
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from services.bi_service import (
    AGG_FUNCS,
    aggregate,
    apply_filters,
    auto_parse_dates,
    compute_kpi,
    detect_column_types,
)

CHART_TYPES = ["Bar", "Line", "Pie", "Area", "Treemap"]


def dashboard_page(df):
    st.success("✅ File Uploaded Successfully")

    # PREVIEW
    
    with st.expander("🔍 Preview Data"):
        st.dataframe(df.head(20), width='stretch')

    st.divider()

    # DATASET OVERVIEW 

    st.subheader("📈 Dataset Overview")

    total_cells = df.shape[0] * df.shape[1]
    missing_cells = int(df.isna().sum().sum())
    quality = ((total_cells - missing_cells) / total_cells * 100) if total_cells > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-card"><h3>📄 Total Rows</h3><h2>{df.shape[0]}</h2></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><h3>📊 Total Columns</h3><h2>{df.shape[1]}</h2></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><h3>⚠ Missing Values</h3><h2>{missing_cells}</h2></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card"><h3>✅ Quality Score</h3><h2>{quality:.1f}%</h2></div>', unsafe_allow_html=True)

    st.divider()

    st.subheader("🎛️ Global Filters (Slicers)")

    working_df = auto_parse_dates(df)
    col_types = detect_column_types(working_df)

    filterable_cols = [c for c, t in col_types.items() if t in ("categorical", "numeric", "date")]

    selected_filter_cols = st.multiselect(
        "Choose columns to filter by",
        filterable_cols,
        default=[c for c, t in col_types.items() if t == "categorical"][:2],
        help="Add any column as a slicer. It will filter the KPI cards and every chart below at once.",
    )

    filters = {}
    if selected_filter_cols:
        filter_cols_ui = st.columns(min(len(selected_filter_cols), 4) or 1)
        for i, col in enumerate(selected_filter_cols):
            with filter_cols_ui[i % len(filter_cols_ui)]:
                col_type = col_types[col]

                if col_type == "categorical":
                    options = sorted(working_df[col].dropna().unique().tolist(), key=str)
                    selected = st.multiselect(f"📌 {col}", options, default=options, key=f"filter_{col}")
                    filters[col] = selected

                elif col_type == "numeric":
                    series = pd.to_numeric(working_df[col], errors="coerce").dropna()
                    if series.empty:
                        continue
                    lo, hi = float(series.min()), float(series.max())
                    if lo == hi:
                        st.caption(f"{col}: only one value ({lo})")
                        continue
                    selected_range = st.slider(f"📌 {col}", lo, hi, (lo, hi), key=f"filter_{col}")
                    filters[col] = selected_range

                elif col_type == "date":
                    series = working_df[col].dropna()
                    if series.empty:
                        continue
                    lo, hi = series.min().date(), series.max().date()
                    if lo == hi:
                        st.caption(f"{col}: only one date ({lo})")
                        continue
                    selected_range = st.date_input(f"📌 {col}", (lo, hi), key=f"filter_{col}")
                    if isinstance(selected_range, tuple) and len(selected_range) == 2:
                        filters[col] = (pd.Timestamp(selected_range[0]), pd.Timestamp(selected_range[1]))

    filtered_df = apply_filters(working_df, filters)
    st.caption(f"Showing {len(filtered_df)} of {len(working_df)} rows after filters.")

    st.session_state.bi_filtered_df = filtered_df

    st.divider()

    # KPI CARDS (with trend vs. previous period)

    st.subheader("📌 KPI Cards")

    numeric_cols = [c for c, t in col_types.items() if t == "numeric"]
    date_cols = [c for c, t in col_types.items() if t == "date"]
    default_date_col = date_cols[0] if date_cols else None

    if not numeric_cols:
        st.info("No numeric columns detected — upload a dataset with numeric fields to see KPI cards.")
    else:
        kpi_cols_selected = st.multiselect(
            "Choose up to 4 KPI measures",
            numeric_cols,
            default=numeric_cols[:4],
            max_selections=4,
            key="kpi_measure_select",
        )

        if kpi_cols_selected:
            kpi_agg = st.selectbox("Aggregation for all KPI cards", list(AGG_FUNCS.keys()), index=0, key="kpi_agg_select")

            kpi_render_cols = st.columns(len(kpi_cols_selected))
            for i, measure in enumerate(kpi_cols_selected):
                kpi = compute_kpi(filtered_df, measure, kpi_agg, date_col=default_date_col)
                with kpi_render_cols[i]:
                    _render_kpi_card(measure, kpi_agg, kpi)

    st.divider()

    st.subheader("📐 Dashboard Charts")

    if "bi_chart_widgets" not in st.session_state:
        st.session_state.bi_chart_widgets = []
        if numeric_cols and filterable_cols:
            default_group = next((c for c, t in col_types.items() if t == "categorical"), None)
            st.session_state.bi_chart_widgets.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "chart_type": "Bar",
                    "group_by": default_group,
                    "measure": numeric_cols[0],
                    "agg": "Sum",
                }
            )

    add_col, _ = st.columns([1, 5])
    with add_col:
        if st.button("➕ Add Chart", width='stretch'):
            st.session_state.bi_chart_widgets.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "chart_type": "Bar",
                    "group_by": None,
                    "measure": numeric_cols[0] if numeric_cols else None,
                    "agg": "Sum",
                }
            )
            st.rerun()

    if not st.session_state.bi_chart_widgets:
        st.info("Click **➕ Add Chart** to build your first dashboard visual.")
    else:
        groupable_cols = [c for c, t in col_types.items() if t in ("categorical", "date")]

        widgets = st.session_state.bi_chart_widgets
        for row_start in range(0, len(widgets), 2):
            row_widgets = widgets[row_start:row_start + 2]
            grid_cols = st.columns(len(row_widgets))

            for grid_col, widget in zip(grid_cols, row_widgets):
                with grid_col:
                    _render_chart_widget(widget, filtered_df, groupable_cols, numeric_cols)


def _render_kpi_card(measure: str, agg_label: str, kpi: dict):
    value = kpi["value"]
    delta_pct = kpi["delta_pct"]
    trend = kpi["trend"]
    sparkline = kpi["sparkline"]

    if trend == "up":
        arrow, color = "▲", "#22c55e"
    elif trend == "down":
        arrow, color = "▼", "#ef4444"
    else:
        arrow, color = "▬", "#94a3b8"

    delta_text = f"{arrow} {abs(delta_pct):.1f}%" if delta_pct is not None else "—"

    try:
        value_display = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
    except (TypeError, ValueError):
        value_display = str(value)

    st.markdown(
        f"""
        <div class="stat-card">
            <h3>{agg_label} of {measure}</h3>
            <h2>{value_display}</h2>
            <p style="color:{color}; margin:0; font-weight:600;">{delta_text} vs previous period</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if len(sparkline) > 1:
        spark_fig = px.line(y=sparkline)
        spark_fig.update_layout(
            height=60,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=False,
            xaxis_visible=False,
            yaxis_visible=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        spark_fig.update_traces(line_color=color)
        st.plotly_chart(spark_fig, width='stretch', config={"displayModeBar": False})


def _render_chart_widget(widget: dict, filtered_df: pd.DataFrame, groupable_cols: list, numeric_cols: list):
    wid = widget["id"]

    with st.container(border=True):
        header_col, remove_col = st.columns([5, 1])
        with header_col:
            st.markdown("**Chart Settings**")
        with remove_col:
            if st.button("✖", key=f"remove_{wid}", help="Remove this chart"):
                st.session_state.bi_chart_widgets = [
                    w for w in st.session_state.bi_chart_widgets if w["id"] != wid
                ]
                st.rerun()

        cfg_cols = st.columns(4)
        with cfg_cols[0]:
            widget["chart_type"] = st.selectbox(
                "Type", CHART_TYPES, index=CHART_TYPES.index(widget["chart_type"]), key=f"type_{wid}"
            )
        with cfg_cols[1]:
            group_options = ["(none)"] + groupable_cols
            current_group = widget["group_by"] if widget["group_by"] in groupable_cols else "(none)"
            selection = st.selectbox("Group By", group_options, index=group_options.index(current_group), key=f"group_{wid}")
            widget["group_by"] = None if selection == "(none)" else selection
        with cfg_cols[2]:
            if numeric_cols:
                measure_idx = numeric_cols.index(widget["measure"]) if widget["measure"] in numeric_cols else 0
                widget["measure"] = st.selectbox("Measure", numeric_cols, index=measure_idx, key=f"measure_{wid}")
            else:
                st.caption("No numeric columns available")
        with cfg_cols[3]:
            widget["agg"] = st.selectbox(
                "Aggregation", list(AGG_FUNCS.keys()), index=list(AGG_FUNCS.keys()).index(widget["agg"]), key=f"agg_{wid}"
            )

        if not widget["measure"]:
            st.warning("No numeric column available to chart.")
            return

        try:
            chart_df = aggregate(filtered_df, widget["group_by"], widget["measure"], widget["agg"])
        except Exception:
            st.error("Could not aggregate this combination — try a different Group By / Measure.")
            return

        if widget["group_by"] is None or widget["group_by"] not in chart_df.columns:
            st.dataframe(chart_df, width='stretch')
            return

        x, y = widget["group_by"], widget["measure"]
        try:
            if widget["chart_type"] == "Bar":
                fig = px.bar(chart_df, x=x, y=y)
            elif widget["chart_type"] == "Line":
                fig = px.line(chart_df, x=x, y=y)
            elif widget["chart_type"] == "Pie":
                fig = px.pie(chart_df, names=x, values=y, hole=0.3)
            elif widget["chart_type"] == "Area":
                fig = px.area(chart_df, x=x, y=y)
            elif widget["chart_type"] == "Treemap":
                fig = px.treemap(chart_df, path=[x], values=y)
            else:
                fig = px.bar(chart_df, x=x, y=y)

            fig.update_layout(
                height=350,
                template="plotly_dark",
                margin=dict(l=10, r=10, t=30, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, width='stretch', key=f"chart_{wid}")
        except Exception:
            st.error("Could not render this chart with the selected settings.")
