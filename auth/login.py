import streamlit as st
from auth.users import USERS


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
                <div class="login-subtitle">Sign in to continue to your dashboard</div>
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

            if (
                username in USERS
                and password == USERS[username]["password"]
            ):

                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = USERS[username]["role"]
                st.query_params["auth"] = "true"
                st.query_params["user"] = username
                st.query_params["role"] = USERS[username]["role"]

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
                © 2026 Data Analysis with A|> | All Rights Reserved
            </div>
            """,
            unsafe_allow_html=True
        )

    st.stop()