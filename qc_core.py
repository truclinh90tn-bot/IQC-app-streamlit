import streamlit as st
import os
import bcrypt

# ===============================
# LOAD CSS
# ===============================
def inject_global_css():
    css_paths = ["assets/theme.css", "theme.css"]
    for p in css_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
            break


def apply_page_config():
    st.set_page_config(
        page_title="IQC – Internal Quality Control",
        layout="wide",
        initial_sidebar_state="expanded",
    )


# ===============================
# AUTH HELPERS
# ===============================
def is_logged_in():
    return st.session_state.get("logged_in", False)


def auth_logout():
    for k in ["logged_in", "username", "lab_id", "role"]:
        st.session_state.pop(k, None)
    st.rerun()


# ===============================
# HERO
# ===============================
def render_hero():
    st.markdown(
        """
        <div class="hero-container">
          <div class="hero-title">
            PHẦN MỀM NỘI KIỂM TRA CHẤT LƯỢNG XÉT NGHIỆM
          </div>
          <div class="hero-sub">
            🧪 Theo dõi IQC, cảnh báo sai số theo Westgard,
            tối ưu hoá nội kiểm dựa trên sigma.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ===============================
# LOGIN UI
# ===============================
def render_login_section():
    st.markdown(
        """
        <div class="login-card">
          <div class="login-title">🔐 Đăng nhập IQC</div>
          <div class="login-desc">
            Nhập tài khoản PXN được cấp để truy cập dữ liệu riêng.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Đăng nhập", use_container_width=True):
            # DEMO – sau này nối Supabase
            if username and password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.lab_id = username.upper()
                st.session_state.role = "pxn"
                st.rerun()
            else:
                st.error("Sai thông tin đăng nhập")


# ===============================
# REQUIRE LOGIN
# ===============================
def require_login():
    if not is_logged_in():
        # Ẩn chữ sidebar
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"] * {
                visibility: hidden;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        render_hero()
        render_login_section()
        st.stop()


# ===============================
# SIDEBAR (SAU LOGIN)
# ===============================
def render_sidebar():
    with st.sidebar:
        st.markdown("### 👤 Phiên đăng nhập")
        st.caption(f"User: {st.session_state.get('username')}")
        st.caption(f"PXN: {st.session_state.get('lab_id')}")
        st.divider()
        if st.button("🚪 Đăng xuất", use_container_width=True):
            auth_logout()

    return {
        "sigma_value": 6,
        "num_levels": 2,
    }
