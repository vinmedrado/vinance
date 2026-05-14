from __future__ import annotations

from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from services.ui_helpers import format_number, format_percent
from services.strategy_interpreter import classify_strategy, calculate_strategy_score

_PALETTE = {
    "green": {"fg": "#047857", "bg": "#ECFDF5", "border": "#A7F3D0", "shadow": "rgba(16,185,129,.18)"},
    "red": {"fg": "#B91C1C", "bg": "#FEF2F2", "border": "#FECACA", "shadow": "rgba(239,68,68,.18)"},
    "dark_red": {"fg": "#7F1D1D", "bg": "#FFF1F2", "border": "#FDA4AF", "shadow": "rgba(127,29,29,.18)"},
    "yellow": {"fg": "#A16207", "bg": "#FFFBEB", "border": "#FDE68A", "shadow": "rgba(245,158,11,.18)"},
    "blue": {"fg": "#1D4ED8", "bg": "#EFF6FF", "border": "#BFDBFE", "shadow": "rgba(37,99,235,.18)"},
    "light_blue": {"fg": "#0369A1", "bg": "#F0F9FF", "border": "#BAE6FD", "shadow": "rgba(14,165,233,.16)"},
    "purple": {"fg": "#6D28D9", "bg": "#F5F3FF", "border": "#DDD6FE", "shadow": "rgba(124,58,237,.16)"},
    "default": {"fg": "#334155", "bg": "#FFFFFF", "border": "#E2E8F0", "shadow": "rgba(15,23,42,.10)"},
}

_LABEL_COLOR = {
    "Excelente": "green",
    "Boa": "blue",
    "Promissora": "yellow",
    "Promissora, mas arriscada": "yellow",
    "Arriscada": "yellow",
    "Conservadora": "light_blue",
    "Fraca": "red",
    "Inviável": "dark_red",
}

_LABEL_EMOJI = {
    "Excelente": "🟢",
    "Boa": "🔵",
    "Promissora": "🟡",
    "Promissora, mas arriscada": "🟡",
    "Arriscada": "🟠",
    "Conservadora": "🔷",
    "Fraca": "🔴",
    "Inviável": "⛔",
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _color(color: str) -> Dict[str, str]:
    return _PALETTE.get(color, _PALETTE["default"])


def _metric_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        return format_number(value, 2)
    return escape(str(value if value is not None else "-"))


def _label_kind(label: str) -> str:
    normalized = str(label or "")
    if normalized.startswith("Promissora"):
        normalized = "Promissora, mas arriscada"
    return _LABEL_COLOR.get(normalized, "default")


def inject_global_css() -> None:
    """Aplica uma identidade visual premium global para o Streamlit."""
    st.markdown(
        """
        <style>
            :root {
                --financeos-navy:#0F172A;
                --financeos-muted:#64748B;
                --financeos-blue:#2563EB;
                --financeos-green:#10B981;
                --financeos-border:#E2E8F0;
                --financeos-card:rgba(255,255,255,.92);
            }
            .stApp {
                background:
                    radial-gradient(circle at 12% 0%, rgba(37,99,235,.13), transparent 34%),
                    radial-gradient(circle at 88% 8%, rgba(16,185,129,.12), transparent 30%),
                    linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 48%, #F8FAFC 100%);
            }
            .block-container { padding-top: 1.35rem; padding-bottom: 4rem; max-width: 1420px; }
            h1, h2, h3 { color: var(--financeos-navy); letter-spacing: -0.035em; }
            p, label, span { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
            [data-testid="stMetric"] {
                background: var(--financeos-card);
                border: 1px solid rgba(226,232,240,.9);
                padding: 18px;
                border-radius: 24px;
                box-shadow: 0 18px 45px rgba(15,23,42,.07);
                backdrop-filter: blur(12px);
            }
            [data-testid="stMetricValue"] { color:#0F172A; font-weight:900; }
            div[data-testid="stDataFrame"] {
                border-radius: 22px;
                overflow: hidden;
                border:1px solid #E2E8F0;
                box-shadow: 0 14px 32px rgba(15,23,42,.06);
            }
            .stButton > button {
                border-radius: 16px;
                border: 0;
                background: linear-gradient(135deg,#2563EB,#1D4ED8);
                color: white;
                font-weight: 900;
                padding: .72rem 1.2rem;
                box-shadow: 0 14px 28px rgba(37,99,235,.22);
            }
            .stButton > button:hover { transform: translateY(-1px); background: linear-gradient(135deg,#1D4ED8,#1E40AF); color:white; }
            .financeos-hero {
                position:relative;
                overflow:hidden;
                padding: 30px 34px;
                border-radius: 34px;
                border: 1px solid rgba(191,219,254,.90);
                background: linear-gradient(135deg, rgba(255,255,255,.96), rgba(239,246,255,.92) 55%, rgba(236,253,245,.84));
                box-shadow: 0 26px 70px rgba(15,23,42,.11);
                margin: 4px 0 26px 0;
            }
            .financeos-hero::after {
                content:"";
                position:absolute;
                right:-90px; top:-120px;
                width:320px; height:320px;
                background: radial-gradient(circle, rgba(37,99,235,.18), transparent 62%);
                border-radius:50%;
            }
            .financeos-eyebrow {
                display:inline-flex; align-items:center; gap:8px;
                padding: 8px 13px;
                border-radius: 999px;
                background: rgba(37,99,235,.10);
                color:#1D4ED8;
                border:1px solid rgba(37,99,235,.18);
                font-size:.78rem; font-weight:950; letter-spacing:.08em; text-transform:uppercase;
            }
            .financeos-title { font-size: clamp(2.2rem, 4.2vw, 4rem); line-height:.98; font-weight: 980; color:#0F172A; margin-top:14px; letter-spacing:-.06em; }
            .financeos-subtitle { color:#475569; font-size:1.04rem; max-width:900px; margin-top:10px; line-height:1.55; }
            .financeos-section {
                margin: 10px 0 20px 0;
                padding: 18px 22px;
                border-radius: 28px;
                background: rgba(255,255,255,.88);
                border: 1px solid rgba(226,232,240,.95);
                box-shadow: 0 16px 42px rgba(15,23,42,.06);
                backdrop-filter: blur(10px);
            }
            .financeos-muted { color:#64748B; font-size:.96rem; }
            details {
                border-radius: 18px !important;
            }
            hr { border-color: rgba(148,163,184,.25); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_global_header() -> None:
    render_hero(
        title="FinanceOS",
        subtitle="Quantitative Wealth Intelligence",
        eyebrow="FinanceOS · SaaS Quant Platform",
        status="Dados · Scores · Backtests · Otimização",
    )


def render_hero(title: str, subtitle: str, eyebrow: str = "FinanceOS", status: Optional[str] = None, metrics: Optional[Dict[str, Any]] = None) -> None:
    metrics_html = ""
    if metrics:
        items = []
        for k, v in metrics.items():
            items.append(
                f"<div style='min-width:130px;padding:12px 14px;border-radius:18px;background:rgba(255,255,255,.78);border:1px solid rgba(226,232,240,.9);'>"
                f"<div style='font-size:.72rem;color:#64748B;font-weight:900;text-transform:uppercase;letter-spacing:.06em;'>{escape(str(k))}</div>"
                f"<div style='font-size:1.18rem;font-weight:950;color:#0F172A;margin-top:2px;'>{escape(str(v))}</div>"
                f"</div>"
            )
        metrics_html = f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-top:20px;'>{''.join(items)}</div>"
    status_html = f"<div class='financeos-subtitle' style='font-weight:800;color:#2563EB;'>{escape(status)}</div>" if status else ""
    st.markdown(
        f"""
        <div class="financeos-hero">
            <div class="financeos-eyebrow">{escape(eyebrow)}</div>
            <div class="financeos-title">{escape(title)}</div>
            <div class="financeos-subtitle">{escape(subtitle)}</div>
            {status_html}
            {metrics_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: Optional[str] = None) -> None:
    subtitle_html = f"<div class='financeos-muted'>{escape(subtitle)}</div>" if subtitle else ""
    st.markdown(
        f"""
        <div class="financeos-section">
            <div style="font-size:1.6rem;font-weight:950;color:#0F172A;letter-spacing:-.035em;">{escape(title)}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: Any, delta: Any = None, color: str = "default") -> None:
    c = _color(color)
    delta_html = ""
    if delta is not None and delta != "":
        delta_html = f"<div style='font-size:.82rem;color:#64748B;margin-top:8px;line-height:1.3;'>{escape(str(delta))}</div>"
    st.markdown(
        f"""
        <div style="background:linear-gradient(180deg,#FFFFFF,{c['bg']});border:1px solid {c['border']};border-radius:28px;padding:22px 24px;
                    box-shadow:0 18px 44px {c['shadow']};min-height:134px;position:relative;overflow:hidden;">
            <div style="position:absolute;right:-34px;top:-34px;width:110px;height:110px;border-radius:50%;background:{c['bg']};opacity:.85;"></div>
            <div style="font-size:.74rem;color:#64748B;text-transform:uppercase;letter-spacing:.09em;font-weight:950;position:relative;">{escape(title)}</div>
            <div style="font-size:2.05rem;line-height:1.1;font-weight:980;color:{c['fg']};margin-top:10px;position:relative;">{_metric_value(value)}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_badge(label: str, kind: Optional[str] = None) -> None:
    display = str(label or "-")
    normalized = display
    if normalized.startswith("Promissora"):
        normalized = "Promissora, mas arriscada"
    color_name = kind or _LABEL_COLOR.get(normalized, "default")
    c = _color(color_name)
    emoji = _LABEL_EMOJI.get(normalized, "")
    st.markdown(
        f"""
        <span style="display:inline-flex;align-items:center;gap:8px;padding:7px 13px;border-radius:999px;
                     background:{c['bg']};color:{c['fg']};border:1px solid {c['border']};
                     font-weight:950;font-size:.86rem;box-shadow:0 10px 24px {c['shadow']};">
            {emoji} {escape(display)}
        </span>
        """,
        unsafe_allow_html=True,
    )


def render_metric_row(metrics: Dict[str, Any]) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Retorno", format_percent(metrics.get("total_return")))
    c2.metric("Drawdown", format_percent(metrics.get("max_drawdown")))
    c3.metric("Sharpe", f"{_num(metrics.get('sharpe_ratio')):.2f}")
    c4.metric("Win rate", format_percent(metrics.get("win_rate")))
    c5.metric("Trades", format_number(metrics.get("total_trades"), 0))
    c6.metric("Turnover", f"{_num(metrics.get('turnover')):.2f}")


def render_strategy_card(strategy_dict: Dict[str, Any], rank: Optional[int] = None, highlight: bool = False, position: Optional[int] = None) -> None:
    rank = rank if rank is not None else position
    label_info = classify_strategy(strategy_dict)
    label = label_info.get("label", "-")
    score = int(strategy_dict.get("comparison_score") or strategy_dict.get("strategy_ui_score") or calculate_strategy_score(strategy_dict))
    title = strategy_dict.get("strategy") or strategy_dict.get("strategy_name") or "Estratégia"
    asset_class = strategy_dict.get("asset_class") or "-"
    top_n = strategy_dict.get("top_n") or "-"
    backtest_id = strategy_dict.get("id") or strategy_dict.get("backtest_id") or "-"
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(int(rank or 0), f"#{rank}" if rank else "")
    border = "#2563EB" if highlight else "#E2E8F0"
    shadow = "0 28px 70px rgba(37,99,235,.20)" if highlight else "0 16px 42px rgba(15,23,42,.08)"
    bg = "linear-gradient(135deg,#FFFFFF,#EFF6FF)" if highlight else "linear-gradient(135deg,#FFFFFF,#F8FAFC)"
    badge_color = _color(_label_kind(label))
    size_score = "2.1rem" if highlight else "1.62rem"

    st.markdown(
        f"""
        <div style="background:{bg};border:1px solid {border};border-radius:30px;padding:{'25px 28px' if highlight else '20px 22px'};
                    box-shadow:{shadow};margin-bottom:16px;position:relative;overflow:hidden;">
            <div style="position:absolute;right:-50px;top:-70px;width:190px;height:190px;border-radius:50%;background:rgba(37,99,235,.10);"></div>
            <div style="display:flex;justify-content:space-between;gap:18px;align-items:flex-start;position:relative;">
                <div>
                    <div style="font-size:.86rem;color:#64748B;font-weight:950;text-transform:uppercase;letter-spacing:.08em;">{escape(str(medal))} Backtest {escape(str(backtest_id))}</div>
                    <div style="font-size:{'1.55rem' if highlight else '1.24rem'};font-weight:980;color:#0F172A;margin-top:4px;letter-spacing:-.04em;">{escape(str(title))}</div>
                    <div style="font-size:.92rem;color:#64748B;margin-top:3px;">{escape(str(asset_class))} · Top N {escape(str(top_n))}</div>
                </div>
                <div style="text-align:right;">
                    <div style="display:inline-block;padding:7px 12px;border-radius:999px;background:{badge_color['bg']};
                                color:{badge_color['fg']};border:1px solid {badge_color['border']};font-weight:950;font-size:.82rem;box-shadow:0 10px 24px {badge_color['shadow']};">
                        {escape(str(label))}
                    </div>
                    <div style="font-size:{size_score};font-weight:980;color:#2563EB;margin-top:9px;">{score}/100</div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px;position:relative;">
                <div><span style="color:#64748B;font-size:.74rem;font-weight:900;text-transform:uppercase;">Retorno</span><br><b style="color:#047857;">{format_percent(strategy_dict.get('total_return'))}</b></div>
                <div><span style="color:#64748B;font-size:.74rem;font-weight:900;text-transform:uppercase;">Drawdown</span><br><b style="color:#B91C1C;">{format_percent(strategy_dict.get('max_drawdown'))}</b></div>
                <div><span style="color:#64748B;font-size:.74rem;font-weight:900;text-transform:uppercase;">Sharpe</span><br><b>{_num(strategy_dict.get('sharpe_ratio')):.2f}</b></div>
                <div><span style="color:#64748B;font-size:.74rem;font-weight:900;text-transform:uppercase;">Turnover</span><br><b>{_num(strategy_dict.get('turnover')):.2f}</b></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top5_cards(strategies: List[Dict[str, Any]]) -> None:
    if not strategies:
        st.info("Ainda não há estratégias para ranquear.")
        return
    top = list(strategies[:5])
    if top:
        render_strategy_card(top[0], rank=1, highlight=True)
    if len(top) > 1:
        cols = st.columns(min(2, len(top) - 1))
        for idx, item in enumerate(top[1:3], start=2):
            with cols[idx - 2]:
                render_strategy_card(item, rank=idx, highlight=False)
    if len(top) > 3:
        with st.expander("Ver #4 e #5", expanded=True):
            cols = st.columns(len(top[3:]))
            for offset, item in enumerate(top[3:], start=4):
                with cols[offset - 4]:
                    render_strategy_card(item, rank=offset, highlight=False)


def render_top5_strategies(strategies: List[Dict[str, Any]]) -> None:
    render_top5_cards(strategies)


def render_comparison_summary(summary: str, kind: str = "info") -> None:
    if kind == "success":
        st.success(summary)
    elif kind == "warning":
        st.warning(summary)
    elif kind == "error":
        st.error(summary)
    else:
        st.info(summary)



def render_empty_state(title: str, message: str, action_label: str | None = None, page: str | None = None) -> None:
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#FFFFFF,#F8FAFC);border:1px dashed #CBD5E1;border-radius:30px;padding:28px;text-align:center;box-shadow:0 16px 36px rgba(15,23,42,.06);">
            <div style="font-size:2rem;margin-bottom:6px;">✨</div>
            <div style="font-size:1.35rem;font-weight:950;color:#0F172A;letter-spacing:-.03em;">{escape(str(title))}</div>
            <div style="color:#64748B;max-width:760px;margin:8px auto 0 auto;line-height:1.55;">{escape(str(message))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if action_label and page:
        st.page_link(page, label=action_label, icon="➡️")


def render_callout(title: str, message: str, kind: str = "info") -> None:
    color = {"info":"blue", "success":"green", "warning":"yellow", "danger":"red"}.get(kind, "blue")
    c = _color(color)
    st.markdown(
        f"""
        <div style="background:{c['bg']};border:1px solid {c['border']};border-radius:24px;padding:18px 20px;box-shadow:0 12px 28px {c['shadow']};min-height:126px;">
            <div style="font-weight:950;color:{c['fg']};font-size:1.08rem;">{escape(str(title))}</div>
            <div style="color:#475569;margin-top:8px;line-height:1.5;">{escape(str(message))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
