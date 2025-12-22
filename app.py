import streamlit as st
import qc_core as qc

qc.apply_page_config()
qc.inject_global_css()

# LOGIN CHECK
qc.require_login()

# SIDEBAR + LOGOUT
cfg = qc.render_sidebar()

# HERO (vẫn giữ sau login)
qc.render_hero()

st.markdown("### 📊 Dashboard nội kiểm – Tổng quan")
st.info("Nội dung dashboard sẽ hiển thị tại đây.")
