import streamlit as st
import pandas as pd
import qc_core as qc

qc.require_login()
qc.require_admin()

st.set_page_config(page_title="Admin • Quản lý tài khoản", layout="wide")
qc.render_global_header()

st.markdown("## 🔐 Admin • Quản lý tài khoản")
st.caption("Tạo user PXN (pxn001/...) - reset mật khẩu - cập nhật role/lab_id - xem audit log.")

# --- Tabs
_tab1, _tab2, _tab3 = st.tabs(["➕ Cấp tài khoản", "🔁 Reset/Cập nhật", "🧾 Audit log"])

with _tab1:
    st.markdown("### ➕ Cấp tài khoản PXN")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        username = st.text_input("Username (vd: pxn001)", value="pxn001")
    with col2:
        lab_id = st.text_input("Mã PXN (lab_id) (vd: PXN001)", value="PXN001")
    with col3:
        role = st.selectbox("Role", ["pxn", "admin"], index=0)

    password = st.text_input("Password", type="password", help="Có thể nhập password theo ý chị.")

    colA, colB = st.columns([1, 2])
    with colA:
        do_create = st.button("✅ Tạo tài khoản", use_container_width=True)
    with colB:
        st.info("Lưu ý: chức năng tạo/reset cần `supabase.service_key` trong Secrets. ")

    if do_create:
        try:
            prof = qc.admin_create_account(username=username, password=password, role=role, lab_id=lab_id)
            st.success(f"Đã tạo: {prof['username']} | role={prof['role']} | lab_id={prof.get('lab_id')}")
        except Exception as e:
            st.error(str(e))

    st.divider()
    st.markdown("### 📋 Danh sách tài khoản (profiles)")
    rows = qc.admin_list_accounts()
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("Chưa đọc được bảng profiles (hoặc chưa có dữ liệu).")


with _tab2:
    st.markdown("### 🔁 Reset mật khẩu / cập nhật role, lab_id")

    rows = qc.admin_list_accounts()
    options = [r.get("username") for r in rows] if rows else []
    sel = st.selectbox("Chọn user", options=options)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        new_pass = st.text_input("Password mới", type="password")
        if st.button("🔁 Reset password", use_container_width=True):
            try:
                qc.admin_reset_password(sel, new_pass)
                st.success("Đã reset password.")
            except Exception as e:
                st.error(str(e))

    with c2:
        new_role = st.selectbox("Role mới", ["pxn", "admin"], index=0)
        if st.button("💾 Cập nhật role", use_container_width=True):
            try:
                qc.admin_update_profile(sel, role=new_role)
                st.success("Đã cập nhật role.")
            except Exception as e:
                st.error(str(e))

    with c3:
        new_lab = st.text_input("lab_id mới", value="")
        if st.button("💾 Cập nhật lab_id", use_container_width=True):
            try:
                qc.admin_update_profile(sel, lab_id=new_lab)
                st.success("Đã cập nhật lab_id.")
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.markdown("### 🚫 Vô hiệu hoá tài khoản")
    st.warning("Thao tác này sẽ 'ban' user trong Supabase Auth. (Có thể bật lại trong Supabase nếu cần)")
    if st.button("🚫 Disable user", type="secondary"):
        try:
            qc.admin_disable_account(sel)
            st.success("Đã disable user.")
        except Exception as e:
            st.error(str(e))


with _tab3:
    st.markdown("### 🧾 Audit log (lịch sử cấp/reset)")
    st.caption("Nếu chưa tạo bảng audit_log thì phần này sẽ trống. Chạy SQL tạo bảng trước.")

    logs = qc.admin_read_audit_log(limit=300)
    if logs:
        df = pd.DataFrame(logs)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có audit log.")
