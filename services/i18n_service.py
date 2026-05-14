
from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "locales"
DEFAULT_LANG = "pt_BR"


def _load(lang: str) -> dict:
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        path = LOCALES_DIR / f"{DEFAULT_LANG}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def t(key: str, lang: str | None = None, default: str | None = None) -> str:
    lang = lang or st.session_state.get("lang") or (st.session_state.get("user") or {}).get("preferred_language") or DEFAULT_LANG
    data = _load(lang)
    cur = data
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            if lang != DEFAULT_LANG:
                return t(key, DEFAULT_LANG, default)
            return default or key
    return str(cur)


def language_selector():
    lang = st.sidebar.selectbox("Idioma / Language", ["pt_BR", "en_US", "es_ES"], index=["pt_BR", "en_US", "es_ES"].index(st.session_state.get("lang", "pt_BR")) if st.session_state.get("lang", "pt_BR") in ["pt_BR", "en_US", "es_ES"] else 0)
    st.session_state["lang"] = lang
    return lang
