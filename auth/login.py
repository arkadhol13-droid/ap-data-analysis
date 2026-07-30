
import streamlit as st

from auth.users import verify_credentials
from security.audit import (
    EVENT_ACCOUNT_LOCKOUT,
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_SUCCESS,
    log_event,
)
from security.lockout import is_locked_out, record_attempt
from security.rate_limiter import enforce_rate_limit
from security.session_manager import create_session
from security.validators import sanitize_text_input
from config.security_settings import LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_SECONDS


def _detect_device(user_agent: str) -> str:
    ua = user_agent or ""
    if "Windows" in ua:
        return "💻 Windows PC"
    if "Android" in ua:
        return "📱 Android"
    if "iPhone" in ua or "iPad" in ua:
        return "📱 iOS"
    if "Mac" in ua:
        return "💻 Mac"
    if "Linux" in ua:
        return "💻 Linux"
    return (ua[:100] if ua else "Unknown Device")


def _client_ip() -> str:
    """
    Best-effort client IP extraction. Streamlit itself does not expose the
    true client IP reliably when behind a reverse proxy; if you deploy
    behind nginx/ALB, forward X-Forwarded-For and have the proxy set it,
    then read it here via st.context.headers. We fall back to "unknown"
    rather than guessing, since a wrong IP is worse than no IP for security
    logging/rate limiting decisions.
    """
    try:
        forwarded = st.context.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    except Exception:
        pass
    return "unknown"


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
            unsafe_allow_html=True,
        )

        logout_notice = st.session_state.pop("logout_notice", None)
        if logout_notice:
            level, message = logout_notice
            getattr(st, level, st.info)(message)

        username_raw = st.text_input(
            "Username",
            placeholder="Enter username",
            label_visibility="collapsed",
            max_chars=32,
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password",
            label_visibility="collapsed",
            max_chars=128,
        )

        login_btn = st.button("Login", use_container_width=True)

        if login_btn:
            # Server-side sanitization -- never trust the raw client input.
            username = sanitize_text_input(username_raw, max_length=32)
            client_ip = _client_ip()
            rl = enforce_rate_limit(
                "login", client_ip, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_SECONDS
            )
            if not rl.allowed:
                st.error(
                    f"Too many login attempts. Please try again in "
                    f"{rl.retry_after_seconds} seconds."
                )
                st.stop()

            if not username:
                st.error("Invalid username or password.")
                st.stop()

            locked, remaining = is_locked_out(username)
            if locked:
                minutes = max(remaining // 60, 1)
                st.error(
                    f"This account is temporarily locked due to repeated "
                    f"failed login attempts. Try again in about {minutes} "
                    f"minute(s)."
                )
                log_event(
                    EVENT_ACCOUNT_LOCKOUT,
                    username=username,
                    details={"ip": client_ip, "remaining_seconds": remaining},
                )
                st.stop()
            role = verify_credentials(username, password)

            if role:
                record_attempt(username, success=True)

                device = _detect_device(
                    (st.context.headers.get("User-Agent", "") if hasattr(st, "context") else "")
                )

                session_id = create_session(
                    username=username,
                    role=role,
                    device=device,
                    ip_address=client_ip,
                )

                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.session_state.session_id = session_id

                log_event(
                    EVENT_LOGIN_SUCCESS,
                    username=username,
                    details={"ip": client_ip, "device": device},
                )

                st.success("Login Successful ✅")
                st.rerun()

            else:
                record_attempt(username, success=False)
                log_event(
                    EVENT_LOGIN_FAILURE,
                    username=username,
                    details={"ip": client_ip},
                )

                remaining_attempts_msg = ""
                locked_now, remaining_now = is_locked_out(username)
                if locked_now:
                    log_event(
                        EVENT_ACCOUNT_LOCKOUT,
                        username=username,
                        details={"ip": client_ip, "remaining_seconds": remaining_now},
                    )
                    st.error(
                        "Too many failed attempts. This account is now "
                        "temporarily locked. Please try again later."
                    )
                else:
                    st.error("Invalid username or password.")

        st.markdown(
            """
            <div class="login-footer">
                © 2026 Data Analysis with A|> |
                All Rights Reserved
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.stop()
