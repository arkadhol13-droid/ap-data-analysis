import streamlit as st
import pandas as pd
from datetime import datetime
import os

from auth.users import load_users


def login():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        return

    left, center, right = st.columns([1.4, 1, 1.4])

    with center:

        st.markdown(
            """
            <span class="login-marker"></span>
            <div class="login-header">
                <div class="login-icon">🔐</div>
                <div class="login-title">Secure Dashboard Login</div>
                <div class="login-subtitle">
                    Sign in to continue to your dashboard
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        username = st.text_input(
            "Username",
            placeholder="Enter username",
            label_visibility="collapsed"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password",
            label_visibility="collapsed"
        )

        login_btn = st.button(
            "Login",
            use_container_width=True
        )

        if login_btn:

            users = load_users()

            if (
                username in users
                and password == users[username]["password"]
            ):

                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = users[username]["role"]

                st.query_params["auth"] = "true"
                st.query_params["user"] = username
                st.query_params["role"] = users[username]["role"]

                try:

                    device = st.context.headers.get(
                        "User-Agent",
                        "Unknown Device"
                    )

                    login_row = pd.DataFrame(
                        [{
                            "Username": username,
                            "Login Time": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "Device": device
                        }]
                    )

                    if os.path.exists("login_history.csv"):

                        login_row.to_csv(
                            "login_history.csv",
                            mode="a",
                            header=False,
                            index=False
                        )

                    else:

                        login_row.to_csv(
                            "login_history.csv",
                            index=False
                        )

                except Exception:
                    pass

                st.success(
                    "Login Successful ✅"
                )

                st.rerun()

            else:

                st.error(
                    "Invalid Username or Password ❌"
                )

        st.markdown(
            """
            <div class="login-footer">
                © 2026 Data Analysis with A|> |
                All Rights Reserved
            </div>
            """,
            unsafe_allow_html=True
        )

    st.stop()