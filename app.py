import streamlit as st

from config.theme import (
    load_theme,
    render_header
)

from auth.login import login
from core.file_loader import load_file

from app_pages.dashboard import dashboard_page
from app_pages.chart_builder import chart_page
from app_pages.pivot_builder import pivot_page
from app_pages.data_cleaning import cleaning_page
from app_pages.ai_insights import ai_page
from app_pages.sql_studio import sql_page
from app_pages.admin import admin_page

# PAGE CONFIG
st.set_page_config(
    page_title="Data Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# THEME
load_theme()
render_header()

if st.query_params.get("auth") == "true":

    if "logged_in" not in st.session_state:

        st.session_state.logged_in = True
        st.session_state.username = "admin"
        st.session_state.role = "Admin"

# LOGIN
login()

# SESSION INIT
if "working_df" not in st.session_state:
    st.session_state.working_df = None

if "undo_stack" not in st.session_state:
    st.session_state.undo_stack = []

if "redo_stack" not in st.session_state:
    st.session_state.redo_stack = []

if "last_uploaded_file_id" not in st.session_state:
    st.session_state.last_uploaded_file_id = None

# SIDEBAR USER INFO
st.sidebar.markdown("## 👤 User")

st.sidebar.write(
    f"""
    **Username:** {st.session_state.username}

    **Role:** {st.session_state.role}
    """
)

if st.session_state.role == "Admin":

    st.sidebar.success(
        "Admin Access Enabled 👑"
    )

else:

    st.sidebar.info(
        "User Access Enabled 👤"
    )
# ADMIN PANEL
admin_page_selected = False

if st.session_state.role == "Admin":

    st.sidebar.divider()

    admin_page_selected = st.sidebar.button(
        "🔐 Admin Panel",
        use_container_width=True
    )
# LOGOUT
if st.sidebar.button(
    "🚪 Logout",
    use_container_width=True
):

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.query_params.clear()

    st.rerun()


# FILE UPLOAD
st.sidebar.divider()

uploaded_file = st.sidebar.file_uploader(
    "📂 Upload CSV / Excel",
    type=["csv", "xlsx"]
)

if admin_page_selected:

    admin_page()
    st.stop()

if uploaded_file is None:

    st.info(
        "📂 Please upload a CSV or Excel file to continue."
    )

    st.stop()

# LOAD FILE
try:

    df = load_file(uploaded_file)

except Exception as e:

    st.error(
        f"File Loading Error: {e}"
    )

    st.stop()

# WORKING DATAFRAME
current_file_id = (
    f"{uploaded_file.name}_"
    f"{uploaded_file.size}_"
    f"{uploaded_file.file_id}"
)

is_new_file = (
    st.session_state.last_uploaded_file_id
    != current_file_id
)

if st.session_state.working_df is None or is_new_file:

    st.session_state.working_df = df.copy()

    st.session_state.last_uploaded_file_id = (
        current_file_id
    )

    st.session_state.undo_stack = []
    st.session_state.redo_stack = []

    st.toast(
        f"✅ Loaded new file: {uploaded_file.name}",
        icon="📂"
    )

# NAVIGATION
st.sidebar.divider()

page = st.sidebar.radio(
    "📑 Navigation",
    [
        "Dashboard",
        "Chart Builder",
        "Pivot Builder",
        "Data Cleaning",
        "AI Insights",
        "SQL Studio"
    ]
)

# PAGE ROUTING
try:

    if admin_page_selected:

        admin_page()

    elif page == "Dashboard":

        dashboard_page(
            st.session_state.working_df
        )

    elif page == "Chart Builder":

        chart_page(
            st.session_state.working_df
        )

    elif page == "Pivot Builder":

        pivot_page(
            st.session_state.working_df
        )

    elif page == "Data Cleaning":

        cleaning_page(
            st.session_state.working_df
        )

    elif page == "AI Insights":

        ai_page(
            st.session_state.working_df
        )

    elif page == "SQL Studio":

        sql_page(
            st.session_state.working_df
        )

except Exception as e:

    st.error(
        f"Page Error: {e}"
    )