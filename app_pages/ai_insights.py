import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from config.security_settings import AI_INSIGHTS_RATE_LIMIT, AI_INSIGHTS_RATE_WINDOW_SECONDS
from security.rate_limiter import enforce_rate_limit
from security.validators import sanitize_text_input
from services.bi_service import (
    auto_parse_dates,
    build_3d_bar_chart,
    build_3d_bubble,
    build_3d_donut,
    build_3d_line_trend,
    build_3d_scatter,
    build_3d_stacked_bar,
    build_3d_surface,
    build_3d_target_chart,
    can_build_3d,
    clean_numeric_like_columns,
    detect_column_types,
)
from services.oracle_service import (
    answer_any_question,
    generate_past_present_future,
    generate_report,
)
from services.business_insights import detect_business_problems, format_finding_markdown
from core.agent_widget import render_state, run_agent_sequence
CLEANED_DF_KEYS = [
    "cleaned_df", "clean_df", "df_cleaned", "cleaned_data",
    "clean_data", "final_df", "df", "data",
]
def get_cleaned_df(fallback_df):
    for key in CLEANED_DF_KEYS:
        if key in st.session_state:
            candidate = st.session_state[key]
            if isinstance(candidate, pd.DataFrame) and not candidate.empty:
                return candidate
    return fallback_df

@st.cache_data(show_spinner=False, ttl=600)
def _cached_detect_business_problems(df, col_types, date_col, metrics):
    return detect_business_problems(df, col_types, date_col, metrics=metrics)


@st.cache_data(show_spinner=False, ttl=600)
def _cached_past_present_future(df, metric, date_col):
    return generate_past_present_future(df, metric, date_col)


@st.cache_data(show_spinner=False, ttl=600)
def _cached_report(df, metrics, date_col):
    return generate_report(df, metrics, date_col)


def ai_page(df):
    st.markdown(
        """
        <div style="text-align:center; margin-bottom: 0.5rem;">
            <h1>🔮 AI Insights</h1>
            <p style="opacity:0.75;">Automatic analysis, forecasting, and Q&A for any kind of dataset — runs fully locally, no API key needed.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = get_cleaned_df(df)
    working_df = clean_numeric_like_columns(df)
    working_df = auto_parse_dates(working_df)
    col_types = detect_column_types(working_df)
    numeric_cols = [c for c, t in col_types.items() if t == "numeric"]
    categorical_cols = [c for c, t in col_types.items() if t == "categorical"]
    date_cols = [c for c, t in col_types.items() if t == "date"]

    if not numeric_cols:
        st.info("Upload a dataset with at least one numeric column to unlock analysis, forecasts, and Q&A.")
        return

    with st.expander("⚙️ Settings", expanded=False):
        selected_metrics = st.multiselect(
            "Metrics to analyze",
            numeric_cols,
            default=numeric_cols[:3],
        )
        date_col = st.selectbox(
            "Time column (for trend & forecasting)",
            ["(none)"] + date_cols,
            index=1 if date_cols else 0,
        )
        date_col = None if date_col == "(none)" else date_col

    if not selected_metrics:
        st.warning("Select at least one metric above.")
        return
    st.divider()
    # BUSINESS HEALTH CHECK
    st.subheader("Business Health Check")

    with st.spinner("Scanning for problems, opportunities, and their root causes..."):
        findings = _cached_detect_business_problems(working_df, col_types, date_col, tuple(selected_metrics))

    if not findings:
        st.success("✅ No significant issues or shifts detected in the selected metrics — things look broadly stable.")
    else:
        high_findings = [f for f in findings if f["priority"] == "high"]
        if high_findings:
            top = high_findings[0]
            focus = top["drill_path"][-1]["category"] if top["drill_path"] else top["metric"]
            st.error(f"**If you can fix only one thing first:** focus on **{focus}** — it's driving the largest measurable {'decline' if top['is_decline'] else 'shift'} in **{top['metric']}**.")

        for finding in findings:
            with st.container(border=True):
                st.markdown(format_finding_markdown(finding))

    st.divider()
    # PAST / PRESENT / FUTURE
    st.subheader("🕰️ Past · Present · Future")

    for metric in selected_metrics:
        with st.container(border=True):
            st.markdown(f"### {metric}")
            ppf = _cached_past_present_future(working_df, metric, date_col)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("🔵 **PAST**")
                st.write(ppf["past"])
            with c2:
                st.markdown("🟢 **PRESENT**")
                st.write(ppf["present"])
            with c3:
                st.markdown("🟣 **FUTURE**")
                st.write(ppf["future"])

            if ppf.get("forecast") and ppf["forecast"].get("forecast"):
                _render_forecast_chart(working_df, date_col, metric, ppf["forecast"])

    st.divider()
    # RECOMMENDATIONS
    st.subheader("🎯 Recommendations")
    report = _cached_report(working_df, tuple(selected_metrics), date_col)
    for rec in report["recommendations"]:
        if rec["priority"] == "high":
            st.error(rec["text"])
        elif rec["priority"] == "opportunity":
            st.success(rec["text"])
        elif rec["priority"] == "medium":
            st.warning(rec["text"])
        else:
            st.info(rec["text"])

    st.divider()
    # 3D EXPLORER 
    if can_build_3d(col_types):
        st.subheader("🧊 3D Explorer")
        st.caption("Rotate, zoom, and hover on any of these — pick the chart type that fits your question.")

        dim_cols = [c for c, t in col_types.items() if t == "categorical"]

        chart_kind = st.selectbox(
            "Chart type",
            ["3D Bar", "3D Stacked Bar", "3D Donut", "3D Scatter", "3D Bubble", "3D Line Trend", "3D Surface", "3D Target vs Current"],
            key="3d_kind",
        )

        fig_3d, grouped_3d = None, None

        if chart_kind == "3D Bar":
            c1, c2, c3 = st.columns(3)
            dimension_col = c1.selectbox("Dimension", dim_cols, key="3d_bar_dim")
            metric_h = c2.selectbox("Height", numeric_cols, key="3d_bar_h")
            spread_opts = ["(none)"] + [c for c in numeric_cols if c != metric_h]
            spread_choice = c3.selectbox("Spread (Y axis)", spread_opts, key="3d_bar_spread")
            metric_spread = None if spread_choice == "(none)" else spread_choice
            fig_3d, grouped_3d = build_3d_bar_chart(working_df, dimension_col, metric_h, metric_spread)

        elif chart_kind == "3D Stacked Bar":
            c1, c2 = st.columns([1, 2])
            dimension_col = c1.selectbox("Dimension", dim_cols, key="3d_stack_dim")
            stack_metrics = c2.multiselect("Metrics to stack", numeric_cols, default=numeric_cols[:2], key="3d_stack_metrics")
            if len(stack_metrics) >= 1:
                fig_3d, grouped_3d = build_3d_stacked_bar(working_df, dimension_col, stack_metrics)
            else:
                st.warning("Pick at least one metric to stack.")

        elif chart_kind == "3D Donut":
            c1, c2 = st.columns(2)
            dimension_col = c1.selectbox("Dimension", dim_cols, key="3d_donut_dim")
            metric_v = c2.selectbox("Value", numeric_cols, key="3d_donut_metric")
            fig_3d, grouped_3d = build_3d_donut(working_df, dimension_col, metric_v)

        elif chart_kind == "3D Scatter":
            c1, c2, c3, c4 = st.columns(4)
            dimension_col = c1.selectbox("Dimension", dim_cols, key="3d_scatter_dim")
            metric_x = c2.selectbox("X axis", numeric_cols, key="3d_scatter_x")
            remaining_y = [c for c in numeric_cols if c != metric_x] or numeric_cols
            metric_y = c3.selectbox("Y axis", remaining_y, key="3d_scatter_y")
            z_options = ["(auto: rank)"] + [c for c in numeric_cols if c not in (metric_x, metric_y)]
            z_choice = c4.selectbox("Z axis", z_options, key="3d_scatter_z")
            metric_z = None if z_choice == "(auto: rank)" else z_choice
            fig_3d, grouped_3d = build_3d_scatter(working_df, dimension_col, metric_x, metric_y, metric_z)

        elif chart_kind == "3D Bubble":
            c1, c2, c3, c4 = st.columns(4)
            dimension_col = c1.selectbox("Dimension", dim_cols, key="3d_bubble_dim")
            metric_x = c2.selectbox("X axis", numeric_cols, key="3d_bubble_x")
            remaining_y = [c for c in numeric_cols if c != metric_x] or numeric_cols
            metric_y = c3.selectbox("Y axis", remaining_y, key="3d_bubble_y")
            remaining_size = [c for c in numeric_cols if c not in (metric_x, metric_y)] or numeric_cols
            metric_size = c4.selectbox("Bubble size", remaining_size, key="3d_bubble_size")
            fig_3d, grouped_3d = build_3d_bubble(working_df, dimension_col, metric_x, metric_y, metric_size)

        elif chart_kind == "3D Line Trend":
            if not date_col:
                st.info("Pick a time column in ⚙️ Settings above to unlock 3D Line Trend.")
            else:
                c1, c2 = st.columns(2)
                dimension_col = c1.selectbox("Compare across", dim_cols, key="3d_line_dim")
                metric_v = c2.selectbox("Metric", numeric_cols, key="3d_line_metric")
                fig_3d, grouped_3d = build_3d_line_trend(working_df, date_col, dimension_col, metric_v)

        elif chart_kind == "3D Surface":
            if not date_col:
                st.info("Pick a time column in ⚙️ Settings above to unlock 3D Surface.")
            else:
                c1, c2 = st.columns(2)
                dimension_col = c1.selectbox("Category axis", dim_cols, key="3d_surf_dim")
                metric_v = c2.selectbox("Metric", numeric_cols, key="3d_surf_metric")
                fig_3d, grouped_3d = build_3d_surface(working_df, date_col, dimension_col, metric_v)

        elif chart_kind == "3D Target vs Current":
            c1, c2, c3 = st.columns(3)
            dimension_col = c1.selectbox("Dimension", dim_cols, key="3d_target_dim")
            metric_v = c2.selectbox("Metric", numeric_cols, key="3d_target_metric")
            target_val = c3.number_input("Target value", value=float(pd.to_numeric(working_df[metric_v], errors="coerce").mean() or 0), key="3d_target_val")
            fig_3d, grouped_3d = build_3d_target_chart(working_df, dimension_col, metric_v, target_val)

        if fig_3d is not None:
            st.plotly_chart(fig_3d, width="stretch", key="ai_insights_3d_chart")
        elif chart_kind not in ("3D Line Trend", "3D Surface") or date_col:
            st.info("Not enough overlapping data across these columns to build this chart.")

    st.divider()
    # CHAT-STYLE Q&A 
    st.subheader("💬 Ask Your Data")
    st.caption(
        'Try: "which city has highest sales", "why is profit declining", '
        '"forecast revenue", "current sales target 2000", "what should I improve"'
    )

    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []

    for role, message in st.session_state.ai_chat_history:
        with st.chat_message(role):
            st.markdown(message)

    question_raw = st.chat_input("Ask about your data...")

    if question_raw:
        username = st.session_state.get("username", "anonymous")
        rl = enforce_rate_limit("ai_insights", username, AI_INSIGHTS_RATE_LIMIT, AI_INSIGHTS_RATE_WINDOW_SECONDS)

        if not rl.allowed:
            warn_placeholder = st.empty()
            render_state(
                warn_placeholder,
                "warning",
                "⚠️ Rate Limit",
                f"Max {AI_INSIGHTS_RATE_LIMIT} questions per {AI_INSIGHTS_RATE_WINDOW_SECONDS}s. "
                f"Retry in {rl.retry_after_seconds}s.",
            )
        else:
            question = sanitize_text_input(question_raw, max_length=300)

            st.session_state.ai_chat_history.append(("user", question))
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                agent_placeholder = st.empty()
                run_agent_sequence(agent_placeholder)
                answer = answer_any_question(working_df, question, col_types, numeric_cols, date_col)
                agent_placeholder.empty()
                st.markdown(answer)

            st.session_state.ai_chat_history.append(("assistant", answer))

    if st.session_state.ai_chat_history:
        if st.button("🗑️ Clear conversation"):
            st.session_state.ai_chat_history = []
            st.rerun()
def _render_forecast_chart(df: pd.DataFrame, date_col: str, metric: str, forecast: dict):
    if not date_col or date_col not in df.columns:
        return

    working = df[[date_col, metric]].dropna().sort_values(date_col)
    if working.empty:
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=working[date_col],
            y=pd.to_numeric(working[metric], errors="coerce"),
            mode="lines+markers",
            name="Historical",
            line=dict(color="#2563EB"),
        )
    )

    if forecast.get("forecast"):
        last_x = working[date_col].iloc[-1]
        last_y = pd.to_numeric(working[metric], errors="coerce").iloc[-1]
        future_x = [last_x] + list(forecast["future_labels"])
        future_y = [last_y] + forecast["forecast"]
        fig.add_trace(
            go.Scatter(
                x=future_x, y=future_y, mode="lines+markers", name="Forecast",
                line=dict(color="#f59e0b", dash="dash"),
            )
        )

    fig.update_layout(
        height=280, template="plotly_dark",
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, width="stretch", key=f"forecast_{metric}")
