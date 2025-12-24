"""
auth.py — Authentication (login/logout) for IQC Streamlit app.

- Uses Supabase Auth (email/password) so that Postgres RLS policies apply.
- UX: provides a professional login section (card) that can be placed under the hero banner.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import streamlit as st

from supabase_client import get_supabase_client_public


SESSION_AUTH_OK = "auth_ok"
SESSION_CURRENT_USER = "current_user"


def is_logged_in() -> bool:
    return bool(st.session_state.get(SESSION_AUTH_OK))


def get_current_user() -> Dict[str, Any]:
    """Return current user dict {username, role, lab_id} or {}."""
    u = st.session_state.get(SESSION_CURRENT_USER)
    return u if isinstance(u, dict) else {}


def auth_logout() -> None:
    """Clear auth session and rerun."""
    for k in [
        SESSION_AUTH_OK,
        SESSION_CURRENT_USER,
        "username",
        "role",
        "lab_id",
        "auth_user",
        "auth_role",
        "auth_lab_id",
        "is_logged_in",
    ]:
        st.session_state.pop(k, None)

    # also clear login form keys if present
    for k in ["login_user", "login_pass"]:
        st.session_state.pop(k, None)

    _rerun()


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def _username_to_email(username: str) -> str:
    """Map 'pxn001' -> 'pxn001@iqc.local'."""
    u = (username or "").strip().lower()
    return f"{u}@iqc.local"


def _do_login(username: str, password: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    Perform login via Supabase Auth and fetch profile mapping.
    Returns (ok, user_dict, error_message).
    """
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        return False, {}, "Vui lòng nhập đầy đủ username và password."

    try:
        supabase = get_supabase_client_public()
    except Exception as e:
        return False, {}, f"Chưa cấu hình Supabase đúng: {e}"

    email = _username_to_email(username)

    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as e:
        return False, {}, f"Lỗi đăng nhập Supabase Auth: {e}"

    if not getattr(res, "user", None):
        return False, {}, "Sai username hoặc password."

    try:
        prof = (
            supabase.table("profiles")
            .select("username, role, lab_id")
            .eq("user_id", res.user.id)
            .single()
            .execute()
        )
        data = getattr(prof, "data", None) or {}
        if not data:
            return False, {}, "Tài khoản chưa được gán PXN (profiles). Liên hệ admin."
    except Exception as e:
        return False, {}, f"Không đọc được profiles: {e}"

    user_dict = {
        "username": data.get("username") or username,
        "role": data.get("role") or "pxn",
        "lab_id": data.get("lab_id") or "",
    }
    if not user_dict["lab_id"]:
        return False, {}, "Tài khoản chưa có lab_id. Liên hệ admin."

    return True, user_dict, ""


def render_login_section(
    *,
    title: str = "🔐 Đăng nhập IQC",
    subtitle: str = "Nhập tài khoản PXN được cấp để truy cập dữ liệu riêng.",
    username_key: str = "login_user",
    password_key: str = "login_pass",
) -> None:
    """
    Render a professional login card section (place under hero banner).
    When login succeeds, it sets session and reruns.
    """
    st.markdown('<div class="login-section">', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="login-card">
            <div class="login-title">{title}</div>
            <div class="login-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    username = st.text_input("Username", key=username_key)
    password = st.text_input("Password", type="password", key=password_key)

    if st.button("Đăng nhập", use_container_width=True):
        ok, user, err = _do_login(username, password)
        if ok:
            st.session_state[SESSION_AUTH_OK] = True
            st.session_state[SESSION_CURRENT_USER] = user
            # legacy keys (for existing code)
            st.session_state["username"] = user["username"]
            st.session_state["role"] = user["role"]
            st.session_state["lab_id"] = user["lab_id"]

            st.success(f"✅ Đăng nhập PXN {user['lab_id']} thành công")
            _rerun()
        else:
            st.error(err)

    st.markdown("</div>", unsafe_allow_html=True)


def require_login() -> None:
    """
    Backward-compatible gate.
    If not logged in, show login section and stop.
    Use this when pages call qc.require_login().
    """
    if is_logged_in():
        return

    st.markdown("## ")
    render_login_section()
    st.stop()


def render_logout_button(where: str = "sidebar") -> None:
    """
    Render logout control. where: 'sidebar' or 'main'
    """
    user = get_current_user()
    label = f"🚪 Đăng xuất ({user.get('username','')})" if user else "🚪 Đăng xuất"

    if where == "sidebar":
        with st.sidebar:
            if user:
                st.markdown(
                    f"<div class='user-badge'>👤 <b>{user.get('username','')}</b> "
                    f"<span class='muted'>({user.get('lab_id','')})</span></div>",
                    unsafe_allow_html=True,
                )
            if st.button(label, use_container_width=True):
                auth_logout()
    else:
        if user:
            st.markdown(
                f"<div class='user-badge'>👤 <b>{user.get('username','')}</b> "
                f"<span class='muted'>({user.get('lab_id','')})</span></div>",
                unsafe_allow_html=True,
            )
        if st.button(label, use_container_width=True):
            auth_logout()
