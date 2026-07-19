import streamlit as st


def load_theme():

    try:

        with open(
            "assets/css/custom.css",
            encoding="utf-8"
        ) as f:

            st.markdown(
                f"<style>{f.read()}</style>",
                unsafe_allow_html=True
            )

    except FileNotFoundError:

        st.warning(
            "custom.css file not found."
        )


def render_header():

    st.markdown(
        """
        <div class="main-title">
            📊 Data Analysis with A|>
        </div>

        <div class="sub-title">
            Smart Analytics • Data Cleaning • SQL Studio • AI Insights
        </div>
        """,
        unsafe_allow_html=True
    )


def render_footer():

    st.markdown(
        """
        <hr>

        <div style="
            text-align:center;
            color:#cbd5e1;
            padding:10px;
            font-size:14px;
        ">
            © 2025 A|> Analytics Platform |
            Built with Streamlit 🚀
        </div>
        """,
        unsafe_allow_html=True
    )


def render_page_title(title):

    st.markdown(
        f"""
        <h2 style="
            color:white;
            border-left:5px solid #2563eb;
            padding-left:10px;
            margin-bottom:20px;
        ">
            {title}
        </h2>
        """,
        unsafe_allow_html=True
    )