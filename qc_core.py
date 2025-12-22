import math
import os
import json
from io import BytesIO

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

# Auth + DB (refactored)
from auth import (
    is_logged_in,
    require_login,
    auth_logout,
    render_login_section,
    render_logout_button,
    get_current_user,
)
from supabase_client import (
    supabase_is_configured,
    db_load_state,
    db_save_state,
)


def _rerun():
    """Tương thích nhiều phiên bản Streamlit."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def _img_to_base64(path: str) -> str:
    """Đọc file ảnh và trả về data URI base64 để nhúng vào HTML."""
    try:
        import base64
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(path)[1].lower().replace(".", "")
        mime = "png" if ext in ["png"] else ("jpeg" if ext in ["jpg", "jpeg"] else ext)
        return f"data:image/{mime};base64,{data}"
    except Exception:
        return ""


# =====================================================
# PAGE CONFIG & THEME
# =====================================================

def apply_page_config():
    st.set_page_config(
        page_title="IQC Dashboard",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def get_theme():
    """
    Giữ lại để tương thích code cũ nếu có nơi gọi.
    (Hiện theme chính nằm trong assets/theme.css)
    """
    return {
        "bg": "#F7F9FC",
        "gold": "#B88A2B",
        "goldHover": "#A97A1F",
        "text": "#1F2937",
        "muted": "#6B7280",
    }


def inject_global_css():
    import streamlit as st
    from pathlib import Path

    css_path = Path(__file__).parent / "assets" / "theme.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


# =====================================================
# MULTI-ANALYTE STORE
# =====================================================

def _init_multi_analyte_store():
    """Khởi tạo cấu trúc lưu nhiều xét nghiệm trong session_state."""
    if "iqc_multi" not in st.session_state:
        st.session_state["iqc_multi"] = {}
    if "active_analyte" not in st.session_state:
        st.session_state["active_analyte"] = "Xét nghiệm 1"

    store = st.session_state["iqc_multi"]
    active = st.session_state["active_analyte"]

    if active not in store:
        store[active] = {
            "config": {
                "test_name": active,
                "unit": "",
                "device": "",
                "method": "",
                "qc_name": "",
                "qc_lot": "",
                "qc_expiry": "",
                "num_levels": 2,
                "sigma_value": 6.0,
            },
            "baseline_df": None,
            "qc_stats": None,
            "daily_df": None,
            "z_df": None,
            "summary_df": None,
        }

        # Load saved state (per lab_id + analyte) when available
        try:
            u = get_current_user()
            if u and u.get("lab_id") and supabase_is_configured():
                loaded = db_load_state(u["lab_id"], active)
                if loaded:
                    store[active] = loaded
        except Exception:
            pass

    st.session_state["iqc_multi"] = store
    return store, active


def get_current_analyte_state():
    """Trả về dict state của xét nghiệm đang chọn."""
    store, active = _init_multi_analyte_store()
    return store[active]


def update_current_analyte_state(**kwargs):
    """Cập nhật state cho xét nghiệm đang chọn."""
    store, active = _init_multi_analyte_store()
    cur = store.get(active, {})
    cur.update(kwargs)
    store[active] = cur
    st.session_state["iqc_multi"] = store

    # autosave DB if logged in + configured
    try:
        u = get_current_user()
        if u and u.get("lab_id") and supabase_is_configured():
            db_save_state(u["lab_id"], active, cur)
    except Exception:
        pass


# =====================================================
# SIDEBAR & HEADER
# =====================================================

def render_sidebar():
    """
    Sidebar dùng chung cho tất cả pages.
    Hỗ trợ multi-analyte: chọn / tạo xét nghiệm.
    """
    store, active = _init_multi_analyte_store()

    with st.sidebar:
        logo_path = "assets/qc_logo.png"
        if os.path.exists(logo_path):
            st.image(logo_path, width=120)

        st.markdown('<div class="qc-nav">', unsafe_allow_html=True)
        st.page_link("app.py", label="Trang chủ", icon="🏠")
        st.page_link("pages/1_Thiet_lap_chi_so_thong_ke.py", label="Thiết lập chỉ số thống kê", icon="🧮")
        st.page_link("pages/2_Ghi_nhan_va_danh_gia.py", label="Ghi nhận và đánh giá kết quả", icon="✍️")
        st.page_link("pages/3_Bieu_do_Levey_Jennings.py", label="Levey-Jennings", icon="📈")
        st.page_link("pages/4_Huong_dan_va_About.py", label="Hướng dẫn", icon="📘")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🧬 Chọn xét nghiệm")

        analyte_names = sorted(store.keys())
        if active not in analyte_names:
            analyte_names.insert(0, active)

        selected = st.selectbox(
            "Xét nghiệm đang làm việc",
            analyte_names,
            index=analyte_names.index(active) if active in analyte_names else 0,
        )
        st.session_state["active_analyte"] = selected
        store, active = _init_multi_analyte_store()
        cur = store[active]

        new_name = st.text_input("Tên xét nghiệm mới")
        if st.button("➕ Thêm xét nghiệm mới", use_container_width=True):
            if new_name.strip():
                name = new_name.strip()
                if name not in store:
                    store[name] = {
                        "config": {
                            "test_name": name,
                            "unit": "",
                            "device": "",
                            "method": "",
                            "qc_name": "",
                            "qc_lot": "",
                            "qc_expiry": "",
                            "num_levels": 2,
                            "sigma_value": 6.0,
                        },
                        "baseline_df": None,
                        "qc_stats": None,
                        "daily_df": None,
                        "z_df": None,
                        "summary_df": None,
                    }
                    st.session_state["iqc_multi"] = store
                    st.session_state["active_analyte"] = name
                    _rerun()

        st.markdown("---")

        cfg = cur.get("config", {})
        cfg["don_vi"] = st.text_input("Đơn vị", value=cfg.get("don_vi", ""))
        cfg["test_name"] = st.text_input("Tên xét nghiệm", value=cfg.get("test_name", active))
        cfg["unit"] = st.text_input("Đơn vị đo", value=cfg.get("unit", ""))
        cfg["device"] = st.text_input("Thiết bị", value=cfg.get("device", ""))
        cfg["method"] = st.text_input("Phương pháp", value=cfg.get("method", ""))
        cfg["qc_name"] = st.text_input("Tên QC", value=cfg.get("qc_name", ""))
        cfg["qc_lot"] = st.text_input("Lô QC", value=cfg.get("qc_lot", ""))
        cfg["qc_expiry"] = st.text_input("HSD QC", value=cfg.get("qc_expiry", ""))
        cfg["report_period"] = st.text_input("Kỳ báo cáo (VD: 12/2025)", value=cfg.get("report_period", ""))

        cfg["num_levels"] = st.selectbox("Số mức nồng độ", [2, 3], index=0 if int(cfg.get("num_levels", 2)) == 2 else 1)
        cfg["sigma_value"] = st.number_input("Sigma phương pháp", min_value=1.0, max_value=10.0, value=float(cfg.get("sigma_value", 6.0)), step=0.1)

        cur["config"] = cfg
        store[active] = cur
        st.session_state["iqc_multi"] = store

    return cfg


def render_global_header():
    """Hero banner / header."""
    logo_path = "assets/qc_logo.png"
    logo_data = _img_to_base64(logo_path) if os.path.exists(logo_path) else ""

    st.markdown(
        f"""
        <div class="qc-hero">
          <div style="display:flex; align-items:center; gap:14px;">
            {'<img src="'+logo_data+'" style="height:56px; width:auto;" />' if logo_data else ''}
            <div>
              <h2 style="margin:0;">📊 Dashboard Nội kiểm – IQC</h2>
              <p style="margin:6px 0 0 0;">
                Theo dõi chất lượng xét nghiệm theo Westgard & Levey–Jennings •
                Lưu dữ liệu theo PXN (RLS)
              </p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =====================================================
# SIGMA / RULES
# =====================================================

def get_sigma_category_and_rules(sigma_value: float, num_levels: int):
    sigma_value = float(sigma_value)
    if sigma_value >= 6:
        return "≥ 6σ", ["13s", "22s", "R4s", "41s", "10x"]
    if sigma_value >= 5:
        return "5σ", ["13s", "22s", "R4s"]
    if sigma_value >= 4:
        return "4σ", ["13s", "22s"]
    return "< 4σ", ["12s"]


# =====================================================
# HELPERS: stats, zscore, etc.
# =====================================================

def compute_zscore(x, mean, sd):
    if sd == 0 or sd is None or np.isnan(sd):
        return np.nan
    return (x - mean) / sd


def _safe_float(v, default=np.nan):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _as_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


# =====================================================
# WESTGARD EVALUATION (FULL — from original file)
# =====================================================

def _rule_12s(z):
    return abs(z) > 2


def _rule_13s(z):
    return abs(z) > 3


def _rule_22s(z1, z2):
    # two consecutive controls beyond 2SD on same side
    return (z1 > 2 and z2 > 2) or (z1 < -2 and z2 < -2)


def _rule_r4s(z1, z2):
    return (z1 > 2 and z2 < -2) or (z1 < -2 and z2 > 2) or abs(z1 - z2) > 4


def _rule_41s(z_list):
    # 4 consecutive results beyond 1SD on same side
    if len(z_list) < 4:
        return False
    last4 = z_list[-4:]
    return all(z > 1 for z in last4) or all(z < -1 for z in last4)


def _rule_10x(z_list):
    # 10 consecutive on same side of mean
    if len(z_list) < 10:
        return False
    last10 = z_list[-10:]
    return all(z > 0 for z in last10) or all(z < 0 for z in last10)


def evaluate_westgard(z_df: pd.DataFrame, active_rules):
    """
    Evaluate Westgard rules based on z-score dataframe.
    z_df columns: ['Ngày/Lần', 'Ctrl 1', 'Ctrl 2', ...] or similar
    Returns: summary_df, point_df
    """
    if z_df is None or not isinstance(z_df, pd.DataFrame) or z_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = z_df.copy()
    df.columns = [str(c) for c in df.columns]

    ctrl_cols = [c for c in df.columns if c.lower().startswith("ctrl")]
    if "Ngày/Lần" in df.columns:
        run_col = "Ngày/Lần"
    elif "Run" in df.columns:
        run_col = "Run"
    else:
        run_col = df.columns[0]

    # Prepare lists of per-control z history
    z_hist = {c: [] for c in ctrl_cols}

    summary_rows = []
    point_rows = []

    for i in range(len(df)):
        run = df.iloc[i][run_col]
        ctrl_vals = {c: _safe_float(df.iloc[i][c]) for c in ctrl_cols}

        # update histories
        for c in ctrl_cols:
            z_hist[c].append(ctrl_vals[c])

        rejs = []
        warns = []

        # apply rules
        # 1_2s warning typically
        if "12s" in active_rules:
            for c in ctrl_cols:
                if _rule_12s(ctrl_vals[c]):
                    warns.append(f"12s({c})")

        if "13s" in active_rules:
            for c in ctrl_cols:
                if _rule_13s(ctrl_vals[c]):
                    rejs.append(f"13s({c})")

        if "22s" in active_rules:
            if len(ctrl_cols) >= 2:
                z1 = ctrl_vals[ctrl_cols[0]]
                z2 = ctrl_vals[ctrl_cols[1]]
                if _rule_22s(z1, z2):
                    rejs.append("22s(Ctrl1&2)")
            else:
                # single level: check consecutive in same control
                c = ctrl_cols[0]
                if len(z_hist[c]) >= 2 and _rule_22s(z_hist[c][-2], z_hist[c][-1]):
                    rejs.append(f"22s({c} consecutive)")

        if "R4s" in active_rules and len(ctrl_cols) >= 2:
            z1 = ctrl_vals[ctrl_cols[0]]
            z2 = ctrl_vals[ctrl_cols[1]]
            if _rule_r4s(z1, z2):
                rejs.append("R4s(Ctrl1&2)")

        if "41s" in active_rules:
            for c in ctrl_cols:
                if _rule_41s(z_hist[c]):
                    rejs.append(f"41s({c})")

        if "10x" in active_rules:
            for c in ctrl_cols:
                if _rule_10x(z_hist[c]):
                    rejs.append(f"10x({c})")

        status = "In Control"
        if rejs:
            status = "Out of Control"
        elif warns:
            status = "Warning"

        summary_rows.append(
            {
                "Ngày/Lần": run,
                "Status": status,
                "Rejection rules": "; ".join(rejs),
                "Warning rules": "; ".join(warns),
            }
        )

        # point-level status
        for l, c in enumerate(ctrl_cols):
            p_status = "OK"
            if any(c in msg for msg in rejs):
                p_status = "REJ"
            elif any(c in msg for msg in warns):
                p_status = "WARN"

            all_msgs = rejs + warns
            point_rows.append(
                {
                    "Ngày/Lần": run,
                    "Control": c,
                    "point_status": p_status,
                    "rule_codes": "; ".join(all_msgs),
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    point_df = pd.DataFrame(point_rows)
    return summary_df, point_df


# =====================================================
# LEVEY-JENNINGS CHART (FULL — from original file)
# =====================================================

def create_levey_jennings_chart(
    daily_df: pd.DataFrame,
    mean: float,
    sd: float,
    title: str = "Levey–Jennings",
):
    """
    Create LJ chart in Altair.
    daily_df expects columns: ['Ngày/Lần', 'Ctrl 1', 'Ctrl 2', ...] or similar
    """
    if daily_df is None or not isinstance(daily_df, pd.DataFrame) or daily_df.empty:
        return None

    df = daily_df.copy()
    df.columns = [str(c) for c in df.columns]

    if "Ngày/Lần" in df.columns:
        run_col = "Ngày/Lần"
    elif "Run" in df.columns:
        run_col = "Run"
    else:
        run_col = df.columns[0]

    ctrl_cols = [c for c in df.columns if c.lower().startswith("ctrl")]
    if not ctrl_cols:
        return None

    # melt
    melt = df.melt(id_vars=[run_col], value_vars=ctrl_cols, var_name="Control", value_name="Value")
    melt = melt.dropna(subset=["Value"])
    melt["Value"] = melt["Value"].astype(float)

    # baseline lines
    base = pd.DataFrame(
        {
            "y": [
                mean,
                mean + 1 * sd,
                mean - 1 * sd,
                mean + 2 * sd,
                mean - 2 * sd,
                mean + 3 * sd,
                mean - 3 * sd,
                mean + 3.5 * sd,
                mean - 3.5 * sd,
            ],
            "label": ["Mean", "+1SD", "-1SD", "+2SD", "-2SD", "+3SD", "-3SD", "+3.5SD", "-3.5SD"],
        }
    )

    x = alt.X(f"{run_col}:O", title="Ngày/Lần", sort=None)
    y = alt.Y("Value:Q", title="Giá trị", scale=alt.Scale(zero=False))

    line = (
        alt.Chart(melt)
        .mark_line(point=True)
        .encode(x=x, y=y, color="Control:N", tooltip=[run_col, "Control", "Value"])
        .properties(height=360, title=title)
    )

    mean_line = (
        alt.Chart(pd.DataFrame({run_col: df[run_col].astype(str), "y": mean}))
        .mark_line(strokeDash=[6, 4])
        .encode(x=x, y=alt.Y("y:Q"))
    )

    # SD lines (±1, ±2, ±3 solid) and ±3.5 dashed black
    sd_lines = []
    for k, dash, color in [
        (1, [2, 0], None),
        (2, [2, 0], None),
        (3, [2, 0], None),
    ]:
        for sign in [1, -1]:
            yv = mean + sign * k * sd
            sd_lines.append(
                alt.Chart(pd.DataFrame({run_col: df[run_col].astype(str), "y": yv}))
                .mark_line(opacity=0.6, strokeDash=dash)
                .encode(x=x, y="y:Q")
            )

    for sign in [1, -1]:
        yv = mean + sign * 3.5 * sd
        sd_lines.append(
            alt.Chart(pd.DataFrame({run_col: df[run_col].astype(str), "y": yv}))
            .mark_line(color="black", strokeDash=[6, 4], opacity=0.8)
            .encode(x=x, y="y:Q")
        )

    chart = line + mean_line
    for l in sd_lines:
        chart = chart + l
    return chart


# =====================================================
# CURRENT ANALYTE HELPERS USED BY APP.PY
# =====================================================

def get_current_analyte_key():
    _init_multi_analyte_store()
    return st.session_state.get("active_analyte", "Xét nghiệm 1")


def get_current_analyte_config():
    cur = get_current_analyte_state()
    return cur.get("config", {})


# =====================================================
# HOME DASHBOARD HELPERS (USED BY APP.PY)
# =====================================================

def render_global_header_and_login_landing():
    """
    Helper for layout A:
    Hero on top, login section under hero (when not logged in).
    """
    render_global_header()
    render_login_section()


def get_current_analyte_state_safe():
    try:
        return get_current_analyte_state()
    except Exception:
        return {}


def get_current_analyte_summary():
    cur_state = get_current_analyte_state_safe()
    return cur_state.get("summary_df"), cur_state.get("qc_stats"), cur_state.get("daily_df")


# =====================================================
# EXTRA: compatibility exports (pages may still call qc.require_login)
# =====================================================
# require_login is imported from auth.py already (above)
