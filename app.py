import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config.theme import load_theme, render_header
from config.security_settings import IDLE_TIMEOUT_MINUTES, SESSION_AUTOREFRESH_MS

from auth.login import login
from core.file_loader import load_file

from app_pages.dashboard import dashboard_page
from app_pages.chart_builder import chart_page
from app_pages.pivot_builder import pivot_page
from app_pages.data_cleaning import cleaning_page
from app_pages.ai_insights import ai_page
from app_pages.sql_studio import sql_page
from app_pages.admin import admin_page

from security.audit import EVENT_LOGOUT, EVENT_SESSION_IDLE_TIMEOUT, log_event
from security.session_manager import (
    SessionStatus,
    revoke_session,
    touch_session,
    validate_session,
)
from security.validators import validate_uploaded_filename

# PAGE CONFIG
st.set_page_config(
    page_title="Data Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _force_fresh_check_on_foreground():
    """
    Forces a real, full page reload -- not just a Streamlit in-place
    rerun -- whenever this tab comes back into view. This covers two
    related problems:

    1. Browser back/forward cache (bfcache): Chrome/Safari can restore a
       frozen snapshot of the previous page instead of talking to the
       server again.
    2. Mobile background throttling: when a phone's screen locks or the
       browser tab is backgrounded, mobile browsers pause/throttle JS
       timers (including the periodic st_autorefresh tick below) to save
       battery. That means an admin's "force logout" -- which only takes
       visible effect on the target's next script rerun -- can sit
       undetected for a long time on a phone that's just sitting locked,
       because the timer that would normally catch it never fires while
       backgrounded.

    Listening for `visibilitychange`/`focus` and forcing a hard reload
    the moment the tab/app becomes visible again means the session check
    in app.py always runs immediately when someone looks at their phone
    again, instead of waiting on a timer that may have been paused.
    """
    st.markdown(
        """
        <script>
        function __forceFreshCheck() {
            window.location.reload();
        }
        window.addEventListener('pageshow', function (event) {
            if (event.persisted) { __forceFreshCheck(); }
        });
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'visible') { __forceFreshCheck(); }
        });
        window.addEventListener('focus', __forceFreshCheck);
        </script>
        """,
        unsafe_allow_html=True,
    )

_force_fresh_check_on_foreground()

# THEME
load_theme()
render_header()

login()

session_id = st.session_state.get("session_id")
status = validate_session(session_id)

if status == SessionStatus.REVOKED:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()
    st.session_state["logout_notice"] = (
        "error",
        "🔒 You have been logged out by an administrator, or this session "
        "is no longer valid. Please log in again.",
    )
    st.rerun()

elif status == SessionStatus.IDLE_TIMEOUT:
    log_event(
        EVENT_SESSION_IDLE_TIMEOUT,
        username=st.session_state.get("username"),
        details={"idle_timeout_minutes": IDLE_TIMEOUT_MINUTES},
    )
    revoke_session(session_id, reason="idle_timeout")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()
    st.session_state["logout_notice"] = (
        "warning",
        f"⏱️ You were logged out after {IDLE_TIMEOUT_MINUTES} minutes of "
        f"inactivity. Please log in again.",
    )
    st.rerun()

elif status == SessionStatus.NOT_FOUND:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()
    st.session_state["logout_notice"] = (
        "error",
        "🔒 Session not found. Please log in again.",
    )
    st.rerun()

# status == VALID: refresh last-activity timestamp for this rerun.
touch_session(session_id)

st_autorefresh(interval=SESSION_AUTOREFRESH_MS, key="idle_watchdog")

# SESSION INIT (app-level working state, unrelated to auth)
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
    st.sidebar.success("Admin Access Enabled 👑")
elif st.session_state.role == "Manager":
    st.sidebar.info("Manager Access Enabled 🧭")
else:
    st.sidebar.info("User Access Enabled 👤")

st.sidebar.caption(f"Auto logout after {IDLE_TIMEOUT_MINUTES} minutes of inactivity.")

admin_page_selected = False

if st.session_state.role == "Admin":
    st.sidebar.divider()
    admin_page_selected = st.sidebar.button("🔐 Admin Panel", use_container_width=True)

# LOGOUT
if st.sidebar.button("🚪 Logout", use_container_width=True):
    revoke_session(session_id, reason="user_logout")
    log_event(EVENT_LOGOUT, username=st.session_state.get("username"))

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.query_params.clear()
    st.rerun()

# FILE UPLOAD
st.sidebar.divider()

uploaded_file = st.sidebar.file_uploader(
    "📂 Upload CSV / Excel",
    type=["csv", "xlsx"],
)

if admin_page_selected:
    admin_page()
    st.stop()

if uploaded_file is None:
    st.info("📂 Please upload a CSV or Excel file to continue.")
    st.stop()

valid_name, name_error = validate_uploaded_filename(uploaded_file.name)
if not valid_name:
    st.error(f"Upload rejected: {name_error}")
    st.stop()

# LOAD FILE
try:
    df = load_file(uploaded_file)
except Exception:
    st.error("File Loading Error: the uploaded file could not be read. "
              "Please check the file format and try again.")
    st.stop()

# WORKING DATAFRAME
current_file_id = f"{uploaded_file.name}_{uploaded_file.size}_{uploaded_file.file_id}"
is_new_file = st.session_state.last_uploaded_file_id != current_file_id

if st.session_state.working_df is None or is_new_file:
    st.session_state.working_df = df.copy()
    st.session_state.last_uploaded_file_id = current_file_id
    st.session_state.undo_stack = []
    st.session_state.redo_stack = []
    st.toast(f"✅ Loaded new file: {uploaded_file.name}", icon="📂")

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
        "SQL Studio",
    ],
)

# PAGE ROUTING
try:
    if admin_page_selected:
        admin_page()
    elif page == "Dashboard":
        dashboard_page(st.session_state.working_df)
    elif page == "Chart Builder":
        chart_page(st.session_state.working_df)
    elif page == "Pivot Builder":
        pivot_page(st.session_state.working_df)
    elif page == "Data Cleaning":
        cleaning_page(st.session_state.working_df)
    elif page == "AI Insights":
        ai_page(st.session_state.working_df)
    elif page == "SQL Studio":
        sql_page(st.session_state.working_df)
except Exception:
    st.error("An unexpected error occurred while rendering this page.")