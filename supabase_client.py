"""
supabase_client.py — Supabase client + persistence helpers for IQC Streamlit app.

- Uses public key (publishable/anon) for RLS to apply.
- Provides load/save for iqc_state table.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st

try:
    from supabase import create_client  # type: ignore
except Exception:  # pragma: no cover
    create_client = None


def _get_supabase_secrets() -> Dict[str, Any]:
    sb = st.secrets.get("supabase", {})
    if not isinstance(sb, dict):
        sb = {}
    return sb


def get_public_key() -> str:
    sb = _get_supabase_secrets()
    return sb.get("publishable_key") or sb.get("anon_key") or sb.get("public_key") or ""


def get_secret_key() -> str:
    sb = _get_supabase_secrets()
    return sb.get("secret_key") or sb.get("service_key") or ""


def get_url() -> str:
    sb = _get_supabase_secrets()
    return sb.get("url") or ""


def supabase_is_configured(public: bool = True) -> bool:
    url = get_url()
    key = get_public_key() if public else get_secret_key()
    return bool(url and key and create_client is not None)


@st.cache_resource
def get_supabase_client_public():
    url = get_url()
    key = get_public_key()
    if not url or not key:
        raise RuntimeError("Missing Supabase secrets: supabase.url and supabase.publishable_key (or anon_key)")
    if create_client is None:
        raise RuntimeError("Missing dependency: supabase (pip install supabase)")
    return create_client(url, key)


@st.cache_resource
def get_supabase_client_secret():
    url = get_url()
    key = get_secret_key()
    if not url or not key:
        raise RuntimeError("Missing Supabase secrets: supabase.url and supabase.secret_key (or service_key)")
    if create_client is None:
        raise RuntimeError("Missing dependency: supabase (pip install supabase)")
    return create_client(url, key)


def _df_to_records(df: pd.DataFrame) -> list:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    _df = df.copy()
    for c in _df.columns:
        if np.issubdtype(_df[c].dtype, np.datetime64):
            _df[c] = _df[c].astype("datetime64[ns]").dt.strftime("%Y-%m-%d")
    return _df.to_dict(orient="records")


def _records_to_df(records) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def db_load_state(lab_id: str, analyte_key: str) -> Optional[Dict[str, Any]]:
    if not supabase_is_configured(public=True):
        return None
    try:
        client = get_supabase_client_public()
        resp = (
            client.table("iqc_state")
            .select("state")
            .eq("lab_id", lab_id)
            .eq("analyte_key", analyte_key)
            .limit(1)
            .execute()
        )
        data = getattr(resp, "data", None) or []
        if not data:
            return None
        state = data[0].get("state")
        if not state:
            return None

        out = dict(state)
        for k in ["baseline_df", "qc_stats", "daily_df", "z_df", "summary_df"]:
            v = out.get(k)
            if isinstance(v, list):
                out[k] = _records_to_df(v)
        return out
    except Exception:
        return None


def db_save_state(lab_id: str, analyte_key: str, state: Dict[str, Any]) -> bool:
    if not supabase_is_configured(public=True):
        return False
    try:
        client = get_supabase_client_public()
        payload = dict(state)

        for k in ["baseline_df", "qc_stats", "daily_df", "z_df", "summary_df"]:
            v = payload.get(k)
            if isinstance(v, pd.DataFrame):
                payload[k] = _df_to_records(v)

        client.table("iqc_state").upsert(
            {"lab_id": lab_id, "analyte_key": analyte_key, "state": payload},
            on_conflict="lab_id,analyte_key",
        ).execute()
        return True
    except Exception:
        return False
