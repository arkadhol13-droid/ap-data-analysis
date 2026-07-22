import streamlit as st
import pandas as pd
from datetime import datetime

from auth.users import (
    change_password,
    admin_reset_password,
    load_users
)


def admin_page():

    st.title("🔐 Admin Panel")

    tab1, tab2, tab3 = st.tabs(
        [
            "📜 Login History",
            "🔑 Change Password",
            "👥 Reset User Password"
        ]
    )

    # LOGIN HISTORY

    with tab1:

        st.subheader(
            "User Login History"
        )

        try:

            history = pd.read_csv(
                "login_history.csv"
            )

            if "Login Time" in history.columns:

                now = datetime.now()

                def get_status(login_time):

                    try:

                        login_dt = datetime.strptime(
                            str(login_time),
                            "%Y-%m-%d %H:%M:%S"
                        )

                        diff = now - login_dt

                        mins = int(
                            diff.total_seconds() / 60
                        )

                        if mins <= 5:

                            return "🟢 Active Now"

                        elif mins < 60:

                            return f"🟡 {mins} mins ago"

                        elif mins < 1440:

                            hrs = mins // 60

                            return f"🟡 {hrs} hrs ago"

                        else:

                            days = mins // 1440

                            return f"🔴 {days} days ago"

                    except:

                        return "Unknown"

                history["Status"] = history[
                    "Login Time"
                ].apply(get_status)

            st.dataframe(
                history,
                use_container_width=True
            )

        except Exception:

            st.info(
                "No login history found."
            )

    # CHANGE OWN PASSWORD

    with tab2:

        st.subheader(
            "Change My Password"
        )

        old_password = st.text_input(
            "Current Password",
            type="password"
        )

        new_password = st.text_input(
            "New Password",
            type="password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password"
        )

        if st.button(
            "Update Password"
        ):

            if new_password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            else:

                success = change_password(
                    st.session_state.username,
                    old_password,
                    new_password
                )

                if success:

                    st.success(
                        "Password updated successfully."
                    )

                else:

                    st.error(
                        "Current password incorrect."
                    )

    # ADMIN RESET USER PASSWORD

    with tab3:

        if st.session_state.role == "Admin":

            st.subheader(
                "Reset User Password"
            )

            users = load_users()

            target_user = st.selectbox(
                "Select User",
                list(users.keys())
            )

            new_password = st.text_input(
                "New Password For User",
                type="password",
                key="reset_pass"
            )

            if st.button(
                "Reset Password"
            ):

                admin_reset_password(
                    target_user,
                    new_password
                )

                st.success(
                    f"Password reset for {target_user}"
                )

        else:

            st.warning(
                "Admin access required."
            )