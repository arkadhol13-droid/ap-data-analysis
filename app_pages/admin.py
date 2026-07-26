import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from auth.users import (
    admin_reset_password,
    admin_set_role,
    change_password,
    create_user,
    load_users,
    VALID_ROLES,
)
from security.audit import (
    EVENT_ADMIN_FORCE_LOGOUT,
    EVENT_PASSWORD_CHANGE,
    EVENT_PASSWORD_RESET,
    EVENT_ROLE_CHANGE,
    get_recent_logs,
    log_event,
)
from security.session_manager import (
    list_active_sessions,
    list_all_sessions,
    revoke_all_sessions,
    revoke_session,
    revoke_sessions_for_users,
)
from security.time_utils import to_display_time

def _require_admin() -> bool:
    """
    Defense in depth: even though app.py only shows the Admin Panel button
    to users whose server-side session role is "Admin", we re-check the
    role here too, at the point of use, in case admin_page() is ever
    called from another code path in the future. Never trust that a
    caller already checked -- re-verify server-side, every time.
    """
    if st.session_state.get("role") != "Admin":
        st.error("🚫 Admin access required.")
        return False
    return True

def _fmt_time_ago(iso_timestamp: str) -> str:
    try:
        ts = datetime.fromisoformat(iso_timestamp)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - ts
        mins = int(diff.total_seconds() / 60)

        if mins <= 5:
            return "🟢 Active Now"
        elif mins < 60:
            return f"🟡 {mins} min ago"
        elif mins < 1440:
            return f"🟡 {mins // 60} hr ago"
        else:
            return f"🔴 {mins // 1440} day(s) ago"
    except Exception:
        return "Unknown"

def admin_page():
    if not _require_admin():
        return

    st.title("🔐 Admin Panel")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📜 Login History",
            "🔑 Change Password",
            "👥 User Management",
            "🖥️ Active Sessions",
            "📋 Audit Logs",
            "🚨 Session Control",
        ]
    )

    # TAB 1 — LOGIN HISTORY 

    with tab1:
        st.subheader("Login History")

        logs = get_recent_logs(limit=300)
        login_logs = [
            l for l in logs if l["event_type"] in ("LOGIN_SUCCESS", "LOGIN_FAILURE")
        ]

        if login_logs:
            df = pd.DataFrame(login_logs)
            df["status"] = df["occurred_at"].apply(_fmt_time_ago)
            df["occurred_at"] = df["occurred_at"].apply(to_display_time)
            df = df.rename(
                columns={
                    "occurred_at": "Time (IST)",
                    "event_type": "Event",
                    "username": "Username",
                    "details": "Details",
                    "status": "When",
                }
            )
            st.dataframe(
                df[["Time (IST)", "When", "Event", "Username", "Details"]],
                use_container_width=True,
            )
        else:
            st.info("No login history yet.")

    # TAB 2 — CHANGE MY PASSWORD
    with tab2:
        st.subheader("Change My Password")

        old_password = st.text_input("Current Password", type="password", key="cp_old")
        new_password = st.text_input("New Password", type="password", key="cp_new")
        confirm_password = st.text_input("Confirm New Password", type="password", key="cp_confirm")

        if st.button("Update Password", key="cp_btn"):
            if new_password != confirm_password:
                st.error("New password and confirmation do not match.")
            else:
                success, message = change_password(
                    st.session_state.username, old_password, new_password
                )
                if success:
                    st.success(message)
                    log_event(EVENT_PASSWORD_CHANGE, username=st.session_state.username)
                else:
                    st.error(message)

    # TAB 3 — USER MANAGEMENT 
    with tab3:
        st.subheader("Reset a User's Password")

        users = load_users()
        target_user = st.selectbox("Select User", list(users.keys()), key="reset_user_select")

        reset_password = st.text_input(
            "New Password For User", type="password", key="reset_pass"
        )

        if st.button("Reset Password", key="reset_pass_btn"):
            success, message = admin_reset_password(target_user, reset_password)
            if success:
                st.success(message)
                log_event(
                    EVENT_PASSWORD_RESET,
                    username=target_user,
                    actor=st.session_state.username,
                )
            else:
                st.error(message)

        st.divider()
        st.subheader("Change a User's Role")

        role_target = st.selectbox(
            "Select User", list(users.keys()), key="role_user_select"
        )
        current_role = users.get(role_target, {}).get("role", "User")
        new_role = st.selectbox(
            "New Role",
            VALID_ROLES,
            index=VALID_ROLES.index(current_role) if current_role in VALID_ROLES else 0,
            key="role_select",
        )

        if st.button("Update Role", key="role_btn"):
            success, message = admin_set_role(role_target, new_role)
            if success:
                st.success(message)
                log_event(
                    EVENT_ROLE_CHANGE,
                    username=role_target,
                    actor=st.session_state.username,
                    details={"old_role": current_role, "new_role": new_role},
                )
            else:
                st.error(message)

        st.divider()
        st.subheader("Create New User")

        new_username = st.text_input("Username", key="new_user_name")
        new_user_password = st.text_input(
            "Password", type="password", key="new_user_password"
        )
        new_user_role = st.selectbox("Role", VALID_ROLES, key="new_user_role")

        if st.button("Create User", key="create_user_btn"):
            success, message = create_user(new_username, new_user_password, new_user_role)
            if success:
                st.success(message)
                log_event(
                    "USER_CREATED",
                    username=new_username,
                    actor=st.session_state.username,
                    details={"role": new_user_role},
                )
            else:
                st.error(message)

    # TAB 4 — ACTIVE SESSIONS 
    with tab4:
        st.subheader("Active Sessions (All Users, All Devices)")

        sessions = list_active_sessions()

        if not sessions:
            st.info("No active sessions right now.")
        else:
            for s in sessions:
                cols = st.columns([2, 2, 2, 2, 1.5])
                cols[0].write(f"**{s['username']}**  \n_{s['role']}_")
                cols[1].write(s.get("device") or "Unknown device")
                cols[2].write(s.get("ip_address") or "unknown")
                cols[3].write(_fmt_time_ago(s["last_activity"]))
                if cols[4].button("Force Logout", key=f"logout_{s['session_id']}"):
                    revoke_session(s["session_id"], reason="admin_force_logout")
                    log_event(
                        EVENT_ADMIN_FORCE_LOGOUT,
                        username=s["username"],
                        actor=st.session_state.username,
                        details={"session_id": s["session_id"][:12] + "...", "scope": "single_session"},
                    )
                    st.success(f"Session for {s['username']} ({s.get('device')}) has been logged out.")
                    st.rerun()

    # TAB 5 — AUDIT LOGS
    with tab5:
        st.subheader("Audit Logs")

        logs = get_recent_logs(limit=500)
        if logs:
            df = pd.DataFrame(logs)
            df["occurred_at"] = df["occurred_at"].apply(to_display_time)
            df = df.rename(
                columns={
                    "occurred_at": "Time (IST)",
                    "event_type": "Event",
                    "username": "Username",
                    "actor": "Performed By",
                    "details": "Details",
                }
            )

            event_types = ["All"] + sorted(df["Event"].unique().tolist())
            selected_event = st.selectbox("Filter by event type", event_types)

            if selected_event != "All":
                df = df[df["Event"] == selected_event]

            st.dataframe(df, use_container_width=True)
        else:
            st.info("No audit events recorded yet.")

    # TAB 6 — SESSION CONTROL 
    with tab6:
        st.subheader("Bulk Session Control")

        all_sessions = list_active_sessions()
        active_usernames = sorted({s["username"] for s in all_sessions})

        st.markdown("#### Log out specific user(s), all their devices")
        selected_users = st.multiselect(
            "Select user(s) to force-logout everywhere",
            active_usernames,
            key="bulk_logout_users",
        )

        if st.button("🚪 Force Logout Selected User(s)", key="bulk_logout_btn"):
            if not selected_users:
                st.warning("Select at least one user first.")
            else:
                revoke_sessions_for_users(selected_users, reason="admin_force_logout")
                log_event(
                    EVENT_ADMIN_FORCE_LOGOUT,
                    actor=st.session_state.username,
                    details={"scope": "selected_users", "users": selected_users},
                )
                st.success(f"Logged out all devices for: {', '.join(selected_users)}")
                st.rerun()

        st.divider()

        st.markdown("#### Log out EVERYONE currently active")
        st.caption(
            "This immediately revokes every active session for every user "
            "(including yourself). Everyone will need to log in again."
        )
        confirm = st.checkbox("I understand this will log out all users, including me.", key="confirm_all")

        if st.button("🚨 Force Logout ALL Active Users", key="bulk_logout_all_btn", disabled=not confirm):
            revoke_all_sessions(reason="admin_force_logout_all")
            log_event(
                EVENT_ADMIN_FORCE_LOGOUT,
                actor=st.session_state.username,
                details={"scope": "all_users"},
            )
            st.success("All active sessions have been revoked.")
            st.rerun()

        st.divider()
        st.markdown("#### Recent Session Activity (last 200, including expired/revoked)")
        recent = list_all_sessions(limit=200)
        if recent:
            df = pd.DataFrame(recent)[
                ["username", "role", "device", "ip_address", "created_at",
                 "last_activity", "revoked", "revoked_reason"]
            ].copy()
            df["created_at"] = df["created_at"].apply(to_display_time)
            df["last_activity"] = df["last_activity"].apply(to_display_time)
            df = df.rename(
                columns={"created_at": "Created (IST)", "last_activity": "Last Activity (IST)"}
            )
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No session history yet.")
