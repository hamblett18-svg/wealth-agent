#!/usr/bin/env python3
"""
AI Workforce Solutions — Wealth Intelligence Platform
Streamlit UI  |  Run: streamlit run app.py
"""

import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime

import anthropic
import streamlit as st
import pandas as pd

try:
    import pdf_filler as _pdf_filler
    _PDF_FILL_AVAILABLE = True
except Exception:
    _PDF_FILL_AVAILABLE = False

# ── Resolve paths regardless of CWD ──────────────────────────────────────────
HERE = Path(__file__).parent.resolve()
os.chdir(HERE)
sys.path.insert(0, str(HERE))

from wealth_agent import (
    DATA_DIR, CLIENTS_DIR, MockSalesforce,
    _fmt_money, _safe_float, _build_one_pager,
    create_dummy_data, create_salesforce_contact,
    find_client_file, list_excel_sheets, read_excel_sheet,
)

# ── Brand constants ───────────────────────────────────────────────────────────
BRAND   = "AI Workforce Solutions"
PRODUCT = "Wealth Intelligence Platform"

# ── Page config (MUST be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title=f"{BRAND}",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

HAS_API_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))

# ── Form catalog ──────────────────────────────────────────────────────────────
FORMS_DIR = HERE / "forms"

FORM_CATALOG = {
    "IWSPersonalApp": {
        "label": "IWS Personal / Joint Account Application",
        "file":  "IWSPersonalApp_Dec2024.pdf",
        "desc":  "Required for all Individual and Joint Brokerage / IRA accounts.",
        "acct_types": ["Individual", "Joint Brokerage", "Traditional IRA", "Roth IRA", "Inherited IRA"],
        "fields": [
            "Account Holder 1 – First Name", "Account Holder 1 – Last Name",
            "Account Holder 1 – DOB", "Account Holder 1 – SSN",
            "Account Holder 2 – First Name", "Account Holder 2 – Last Name",
            "Account Holder 2 – DOB", "Account Holder 2 – SSN",
            "Address", "City", "State", "ZIP", "Phone", "Email",
            "Employer", "Occupation", "Annual Income",
            "Investment Objective", "Risk Tolerance", "Time Horizon",
            "Advisor G-Number",
        ],
    },
    "IWSTrustApp": {
        "label": "IWS Trust Account Application",
        "file":  "IWSTrustApp_Dec2024.pdf",  # renamed from "(1)" copy
        "desc":  "Required for all Trust, Estate, or Entity accounts.",
        "acct_types": ["Trust", "Estate", "LLC", "Partnership"],
        "fields": [
            "Trust Name", "Trust Date", "Tax ID (EIN)",
            "Trustee 1 – First Name", "Trustee 1 – Last Name",
            "Trustee 2 – First Name", "Trustee 2 – Last Name",
            "Grantor Name", "Address", "City", "State", "ZIP",
            "Advisor G-Number",
        ],
    },
    "AddRemoveAdvisor": {
        "label": "Add / Remove Advisor – Brokerage",
        "file":  "Add_RemoveAdvisor_Brokerage_Jan2026.pdf",
        "desc":  "Required when client already has a Fidelity account and is adding the advisor.",
        "acct_types": ["Add Advisor to Existing Account"],
        "fields": [
            "Account Holder Name", "Existing Account Number",
            "Custodian (Fidelity / Schwab / etc.)",
            "Advisor Name", "Advisor G-Number", "Action (Add / Remove)",
        ],
    },
    "JournalRequest": {
        "label": "Journal / Internal Transfer Request",
        "file":  "JournalRequest_May2021_rev.pdf",
        "desc":  "Internal transfer between two accounts at the same custodian.",
        "acct_types": ["Internal Transfer"],
        "fields": [
            "From Account – Account Holder", "From Account – Account Number",
            "To Account – Account Holder",   "To Account – Account Number",
            "Transfer Amount", "Transfer Date", "Notes",
        ],
    },
}

ACCOUNT_TYPE_FORMS = {
    "Individual":              ["IWSPersonalApp", "AddRemoveAdvisor"],
    "Joint Brokerage":         ["IWSPersonalApp", "AddRemoveAdvisor"],
    "Traditional IRA":         ["IWSPersonalApp", "AddRemoveAdvisor"],
    "Roth IRA":                ["IWSPersonalApp", "AddRemoveAdvisor"],
    "Inherited IRA":           ["IWSPersonalApp"],
    "Trust":                   ["IWSTrustApp",    "AddRemoveAdvisor"],
    "LLC / Business":          ["IWSTrustApp"],
    "Internal Transfer":       ["JournalRequest"],
    "Add Advisor to Existing": ["AddRemoveAdvisor"],
}

# ─────────────────────────────────────────────────────────────────────────────
# CSS — Futuristic AI theme
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Variables ── */
:root {
  --bg:       #060D1A;
  --bg2:      #0A1628;
  --bg3:      #0E1E38;
  --card:     rgba(10,22,40,0.85);
  --glass:    rgba(255,255,255,0.03);
  --cyan:     #00D4FF;
  --cyan2:    #38BDF8;
  --cyan-dim: rgba(0,212,255,0.18);
  --purple:   #A78BFA;
  --purple2:  #7C3AED;
  --green:    #10B981;
  --amber:    #F59E0B;
  --red:      #EF4444;
  --border:   rgba(0,212,255,0.12);
  --border2:  rgba(0,212,255,0.25);
  --txt:      #E2E8F0;
  --txt2:     #94A3B8;
  --txt3:     #475569;
  --glow-sm:  0 0 12px rgba(0,212,255,0.25);
  --glow-md:  0 0 24px rgba(0,212,255,0.35);
  --glow-lg:  0 0 40px rgba(0,212,255,0.2), 0 0 80px rgba(124,58,237,0.1);
}

/* ── Base — force light text everywhere in main area ── */
html, body, [class*="css"] {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  color: var(--txt) !important;
}
.stApp {
  background: var(--bg) !important;
  color: var(--txt) !important;
}

/* Main content text — override Streamlit's black defaults */
.main p,
.main span,
.main div,
.main li,
.main label,
.main h1, .main h2, .main h3, .main h4,
.stMarkdown p,
.stMarkdown span,
.stMarkdown li,
.stMarkdown strong,
.stMarkdown em,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] strong,
[data-testid="column"] p,
[data-testid="column"] span,
[data-testid="column"] li {
  color: #CBD5E1 !important;
}

/* Labels for inputs/radio/checkbox in main area */
.main label p,
.main .stRadio label p,
.main .stCheckbox label p,
.main [data-testid="stRadio"] label p,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {
  color: #94A3B8 !important;
}

/* Strong / bold text slightly brighter */
.main .stMarkdown strong,
[data-testid="stMarkdownContainer"] strong {
  color: #E2E8F0 !important;
}

/* st.info / st.warning / st.success / st.error text */
[data-testid="stAlert"] p,
[data-testid="stAlert"] span {
  color: #CBD5E1 !important;
}
.stApp::before {
  content: '';
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background:
    radial-gradient(ellipse 80% 50% at 20% -10%, rgba(0,212,255,0.06) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 110%, rgba(124,58,237,0.05) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
}
.main .block-container {
  padding-top: 1.25rem;
  padding-bottom: 5rem;
  max-width: 1440px;
  position: relative;
  z-index: 1;
}
footer { visibility: hidden; }

/* ── Sidebar ── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {
  background: linear-gradient(180deg, #04090F 0%, #060D1A 40%, #08111F 100%) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] span { color: var(--txt3) !important; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] label p,
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stRadio label p,
[data-testid="stSidebar"] [data-testid="stRadio"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] label p,
[data-testid="stSidebar"] [data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p {
  color: #CBD5E1 !important;
  font-weight: 500 !important;
}
[data-testid="stSidebar"] .stCaption p { color: var(--txt3) !important; }
[data-testid="stSidebar"] hr {
  border-color: var(--border) !important;
  margin: 0.75rem 0 !important;
}
[data-testid="stSidebar"] .stButton > button {
  background: var(--glass) !important;
  border: 1px solid var(--border2) !important;
  color: var(--cyan) !important;
  border-radius: 6px !important;
  font-size: 0.8rem !important;
  font-weight: 500 !important;
  width: 100%;
  transition: all 0.2s ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--cyan-dim) !important;
  box-shadow: var(--glow-sm) !important;
}

/* ── Typography ── */
h1, h2, h3 {
  color: var(--txt) !important;
  letter-spacing: -0.01em;
}
h1 { font-size: 1.55rem !important; font-weight: 800 !important; }
h2 { font-size: 1.05rem !important; font-weight: 700 !important; }
h3 { font-size: 0.88rem !important; font-weight: 600 !important; }

/* ── Primary buttons ── */
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(124,58,237,0.15)) !important;
  color: var(--cyan) !important;
  border: 1px solid var(--border2) !important;
  border-radius: 7px !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.03em !important;
  padding: 0.5rem 1.4rem !important;
  transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, rgba(0,212,255,0.25), rgba(124,58,237,0.25)) !important;
  box-shadow: var(--glow-sm) !important;
  transform: translateY(-1px) !important;
}
.stButton > button:not([kind="primary"]) {
  background: var(--glass) !important;
  color: var(--txt2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 7px !important;
  font-weight: 500 !important;
  font-size: 0.85rem !important;
}
.stButton > button:not([kind="primary"]):hover {
  background: rgba(255,255,255,0.05) !important;
  color: var(--txt) !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"],
[data-testid="stMetric"] {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  padding: 1rem 1.25rem !important;
  box-shadow: 0 1px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04) !important;
  border-left: 3px solid var(--cyan) !important;
  backdrop-filter: blur(12px) !important;
}
[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] {
  color: var(--txt3) !important;
  font-size: 0.64rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.1em !important;
}
[data-testid="stMetricValue"] {
  color: var(--cyan) !important;
  font-weight: 800 !important;
  font-family: 'JetBrains Mono', monospace !important;
}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  overflow: hidden !important;
  background: var(--card) !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
  border-radius: 8px !important;
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
}

/* ── Chat ── */
[data-testid="stChatMessage"] {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  margin-bottom: 0.6rem !important;
  backdrop-filter: blur(8px) !important;
}

/* ── Inputs / Selects ── */
.stSelectbox [data-baseweb="select"] > div,
.stTextInput input,
.stTextArea textarea {
  border-radius: 7px !important;
  border-color: var(--border) !important;
  background: var(--bg2) !important;
  color: var(--txt) !important;
}
.stSelectbox [data-baseweb="select"] > div {
  color: var(--txt) !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  color: var(--txt2) !important;
  font-size: 0.86rem !important;
}
.streamlit-expanderContent {
  background: rgba(6,13,26,0.6) !important;
  border: 1px solid var(--border) !important;
  border-top: none !important;
}

/* ── Divider ── */
hr {
  border-color: var(--border) !important;
  margin: 1.25rem 0 !important;
}

/* ── Status widget ── */
[data-testid="stStatusWidget"] {
  border-radius: 8px !important;
  border: 1px solid var(--border) !important;
  background: var(--card) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
  border: 2px dashed var(--border2) !important;
  border-radius: 10px !important;
  background: rgba(0,212,255,0.02) !important;
}

/* ── Radio ── */
[data-testid="stRadio"] > div {
  background: transparent !important;
}

/* ── Checkbox ── */
.stCheckbox label p { color: var(--txt2) !important; }

/* ── Info/warning/success/error native boxes ── */
.stInfo    { background: rgba(0,212,255,0.06) !important; border-color: rgba(0,212,255,0.25) !important; }
.stWarning { background: rgba(245,158,11,0.06) !important; border-color: rgba(245,158,11,0.25) !important; }
.stSuccess { background: rgba(16,185,129,0.06) !important; border-color: rgba(16,185,129,0.25) !important; }
.stError   { background: rgba(239,68,68,0.06) !important; border-color: rgba(239,68,68,0.25) !important; }

/* ── Caption ── */
.stCaption p { color: #64748B !important; font-size: 0.75rem !important; }

/* ── Selectbox dropdown text ── */
.stSelectbox [data-baseweb="select"] span,
.stSelectbox [data-baseweb="select"] div[class*="placeholder"],
.stSelectbox [data-baseweb="menu"] li {
  color: #CBD5E1 !important;
}

/* ── Text input typed text ── */
.stTextInput input, .stTextArea textarea {
  color: #E2E8F0 !important;
}

/* ── Expander header text ── */
.streamlit-expanderHeader p,
.streamlit-expanderHeader span {
  color: #94A3B8 !important;
}

/* ── Code blocks ── */
.stCodeBlock code, pre {
  background: rgba(0,0,0,0.4) !important;
  color: #7DD3FC !important;
}

/* ── Tab-like step indicators ── */
.ai-step-row { display: flex; gap: 0; margin-bottom: 2rem; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
.ai-step { flex: 1; padding: 0.6rem 0.5rem; text-align: center; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; background: var(--bg2); color: var(--txt3); border-right: 1px solid var(--border); transition: all 0.2s; }
.ai-step:last-child { border-right: none; }
.ai-step.active { background: var(--cyan-dim); color: var(--cyan); }
.ai-step.done { background: rgba(16,185,129,0.08); color: #10B981; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HTML UI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _html_page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    icon_html = f'<span style="font-size:1.5rem;margin-right:0.4rem;">{icon}</span>' if icon else ""
    sub_html  = (
        f'<p style="color:#64748B;font-size:0.86rem;margin:0.3rem 0 0;">{subtitle}</p>'
        if subtitle else ""
    )
    st.markdown(f"""
<div style="margin-bottom:1.5rem;">
  <div style="display:flex;align-items:center;">
    {icon_html}
    <h1 style="margin:0;padding:0;background:linear-gradient(135deg,#E2E8F0,#94A3B8);
         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
         background-clip:text;">{title}</h1>
  </div>
  <div style="height:1px;background:linear-gradient(90deg,rgba(0,212,255,0.6) 0%,
       rgba(124,58,237,0.3) 40%,transparent 100%);margin:0.5rem 0 0.3rem;"></div>
  {sub_html}
</div>
""", unsafe_allow_html=True)


def _html_section_header(title: str, icon: str = "") -> None:
    icon_html = f"{icon}&nbsp;" if icon else ""
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.4rem;margin:1.6rem 0 0.6rem;
     padding-bottom:0.4rem;border-bottom:1px solid rgba(0,212,255,0.12);">
  <span style="font-size:0.95rem;">{icon_html}</span>
  <span style="color:rgba(0,212,255,0.8);font-size:0.72rem;font-weight:700;
        text-transform:uppercase;letter-spacing:0.1em;">{title}</span>
</div>
""", unsafe_allow_html=True)


def _html_client_badge(name: str, has_excel: bool, has_registry: bool) -> None:
    tags = []
    if has_registry:
        tags.append(
            '<span style="background:rgba(167,139,250,0.1);color:#A78BFA;border:1px solid '
            'rgba(167,139,250,0.3);border-radius:4px;padding:1px 8px;font-size:0.67rem;'
            'font-weight:700;">📋 Profile</span>'
        )
    if has_excel:
        tags.append(
            '<span style="background:rgba(0,212,255,0.08);color:#38BDF8;border:1px solid '
            'rgba(0,212,255,0.25);border-radius:4px;padding:1px 8px;font-size:0.67rem;'
            'font-weight:700;">📊 Account Data</span>'
        )
    else:
        tags.append(
            '<span style="background:rgba(245,158,11,0.08);color:#F59E0B;border:1px solid '
            'rgba(245,158,11,0.25);border-radius:4px;padding:1px 8px;font-size:0.67rem;'
            'font-weight:700;">⚠ No Account Data</span>'
        )
    initials = "".join(p[0].upper() for p in name.split()[:2]) if name else "?"
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.85rem;padding:0.85rem 1.1rem;
     background:rgba(10,22,40,0.7);border:1px solid rgba(0,212,255,0.15);
     border-radius:10px;margin-bottom:1rem;
     box-shadow:0 0 20px rgba(0,212,255,0.06);backdrop-filter:blur(8px);">
  <div style="width:44px;height:44px;background:linear-gradient(135deg,rgba(0,212,255,0.2),rgba(124,58,237,0.2));
       border:1px solid rgba(0,212,255,0.3);border-radius:50%;
       display:flex;align-items:center;justify-content:center;
       color:#00D4FF;font-size:0.95rem;font-weight:800;flex-shrink:0;
       box-shadow:0 0 12px rgba(0,212,255,0.2);">{initials}</div>
  <div>
    <div style="font-weight:700;color:#E2E8F0;font-size:1.05rem;line-height:1.2;">{name}</div>
    <div style="display:flex;gap:0.3rem;margin-top:4px;">{" ".join(tags)}</div>
  </div>
</div>
""", unsafe_allow_html=True)


def _html_callout(text: str, level: str = "info") -> None:
    cfg = {
        "info":    ("rgba(0,212,255,0.06)",   "#38BDF8", "rgba(0,212,255,0.3)",   "ℹ"),
        "warning": ("rgba(245,158,11,0.06)",  "#F59E0B", "rgba(245,158,11,0.3)",  "⚠"),
        "alert":   ("rgba(239,68,68,0.06)",   "#EF4444", "rgba(239,68,68,0.3)",   "🚨"),
        "success": ("rgba(16,185,129,0.06)",  "#10B981", "rgba(16,185,129,0.3)",  "✓"),
    }
    bg, tc, border, icon = cfg.get(level, cfg["info"])
    st.markdown(f"""
<div style="background:{bg};border-left:3px solid {border};border-radius:0 8px 8px 0;
     padding:0.6rem 1rem;margin:0.4rem 0;font-size:0.87rem;color:{tc};
     backdrop-filter:blur(4px);">
  {icon}&nbsp; {text}
</div>
""", unsafe_allow_html=True)


def _html_stat_row(stats: list) -> None:
    n = len(stats)
    cards = ""
    for label, value in stats:
        cards += f"""
<div style="flex:1;background:rgba(10,22,40,0.7);border:1px solid rgba(0,212,255,0.12);
     border-radius:10px;padding:0.9rem 1.1rem;
     box-shadow:0 0 16px rgba(0,0,0,0.2),inset 0 1px 0 rgba(255,255,255,0.03);
     border-left:3px solid rgba(0,212,255,0.5);backdrop-filter:blur(8px);">
  <div style="color:#475569;font-size:0.62rem;font-weight:700;text-transform:uppercase;
       letter-spacing:0.1em;">{label}</div>
  <div style="color:#00D4FF;font-size:1.25rem;font-weight:800;margin-top:3px;
       font-family:'JetBrains Mono',monospace;">{value}</div>
</div>"""
    st.markdown(
        f'<div style="display:flex;gap:0.75rem;margin:0.75rem 0;">{cards}</div>',
        unsafe_allow_html=True,
    )


def _html_footer() -> None:
    year = datetime.now().year
    st.markdown(f"""
<div style="margin-top:3rem;padding:0.85rem 1.5rem;
     background:linear-gradient(90deg,rgba(0,212,255,0.05),rgba(124,58,237,0.05));
     border:1px solid var(--border);border-radius:10px;
     display:flex;justify-content:space-between;align-items:center;">
  <span style="color:#00D4FF;font-size:0.7rem;font-weight:700;letter-spacing:0.1em;
       text-shadow:0 0 8px rgba(0,212,255,0.4);">
    ⬡ {BRAND.upper()}
  </span>
  <span style="color:#334155;font-size:0.67rem;letter-spacing:0.06em;">
    {PRODUCT} &nbsp;·&nbsp; © {year} &nbsp;·&nbsp; Powered by Claude
  </span>
  <span style="color:#1E293B;font-size:0.67rem;">
    {datetime.now().strftime('%B %d, %Y')}
  </span>
</div>
""", unsafe_allow_html=True)


def _html_step_bar(steps: list, active_idx: int) -> None:
    """Render a horizontal step progress bar. steps = [label,...], active_idx = 0-based."""
    parts = ""
    for i, s in enumerate(steps):
        if i < active_idx:
            cls = "done"
        elif i == active_idx:
            cls = "active"
        else:
            cls = ""
        num = f"{'✓' if i < active_idx else i+1}"
        parts += f'<div class="ai-step {cls}">{num} &nbsp; {s}</div>'
    st.markdown(f'<div class="ai-step-row">{parts}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Client Registry  (data/registered_clients.json)
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY_PATH = DATA_DIR / "registered_clients.json"


def _load_registry() -> list:
    if not REGISTRY_PATH.exists():
        return []
    try:
        return json.loads(REGISTRY_PATH.read_text())
    except Exception:
        return []


def _save_to_registry(name: str, sf_id: str, intake: dict, sf_record: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    records = _load_registry()
    entry = {
        "name":          name,
        "sf_id":         sf_id,
        "registered_at": datetime.utcnow().isoformat() + "Z",
        "intake":        {k: v for k, v in intake.items() if not k.startswith("__")},
        "sf_record":     sf_record,
    }
    updated = [r for r in records if r.get("name", "").lower() != name.lower()]
    updated.append(entry)
    REGISTRY_PATH.write_text(json.dumps(updated, indent=2))


def _registry_names() -> list:
    return [r["name"] for r in _load_registry()]


def _registry_entry(name: str):
    return next((r for r in _load_registry() if r["name"].lower() == name.lower()), None)


# ─────────────────────────────────────────────────────────────────────────────
# Data / parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(val: str) -> str:
    val = val.strip()
    return val.split()[0] if " " in val else val


def _normalize_fields(raw: dict) -> dict:
    out = {}
    for key, val in raw.items():
        k  = key.strip()
        kl = k.lower()
        v  = val.strip()
        if ("first" in kl and "last" in kl) or kl in ("full name", "name"):
            parts = v.split()
            if len(parts) >= 2:
                out["First Name"] = parts[0]
                out["Last Name"]  = parts[-1]
                if len(parts) == 3:
                    out["Middle Initial"] = parts[1]
            else:
                out["First Name"] = v
        elif kl in ("first name", "firstname", "first"):
            out["First Name"] = v
        elif kl in ("last name", "lastname", "last"):
            out["Last Name"] = v
        elif kl in ("dob", "date of birth", "birthdate", "birth date"):
            out["Date of Birth"] = _parse_date(v)
        elif kl == "address":
            out["Address"] = v
        elif kl == "city":
            out["City"] = v
        elif kl == "state":
            out["State"] = v
        elif kl in ("zip", "zip code", "postal code"):
            out["ZIP"] = v
        elif kl == "phone":
            out["Phone"] = v
        elif kl == "email":
            out["Email"] = v
        elif "annual income" in kl:
            out["Annual Income"] = v
        elif "net worth" in kl:
            out["Est. Net Worth"] = v
        elif "liquid" in kl:
            out["Liquid Assets"] = v
        elif kl in ("employer", "company", "firm"):
            out["Employer"] = v
        elif any(x in kl for x in ("occupation", "title", "job title")):
            out["Occupation"] = v
        elif any(x in kl for x in ("investment objective", "objective", "investment goal")):
            out.setdefault("Investment Goal", v)
            out.setdefault("Risk Tolerance",  v)
        elif "risk" in kl and "tolerance" in kl:
            out["Risk Tolerance"] = v
        elif "time horizon" in kl or "horizon" in kl:
            out["Time Horizon (yrs)"] = v
        elif any(x in kl for x in ("referral", "lead source", "referred", "source")):
            out["Referral Source"] = v
        elif "advisor" in kl:
            out.setdefault("Referral Source", v)
        elif "note" in kl or "account" in kl:
            existing = out.get("Notes", "")
            out["Notes"] = (existing + "  " + v).strip() if existing else v
        elif "was" in kl:
            out["WAS"] = v
        elif "fee" in kl:
            out["Fee"] = v
        else:
            out[k] = v
    return out


def _read_intake_form(source):
    read_kw = dict(sheet_name=0, header=None, dtype=str)
    df = pd.read_excel(source, **read_kw) if hasattr(source, "read") else pd.read_excel(str(source), **read_kw)
    df = df.fillna("")
    first_row = [str(v).strip() for v in df.iloc[0]]
    col0 = first_row[0].lower()
    col1 = first_row[1].lower() if len(first_row) > 1 else ""

    if col0 == "field" and col1 == "value":
        raw = {}
        for _, row in df.iloc[1:].iterrows():
            label = str(row.iloc[0]).strip()
            val   = str(row.iloc[1]).strip()
            if label and label.lower() not in ("nan", "none", "field"):
                raw[label] = val
        return [_normalize_fields(raw)]
    else:
        if col0 in ("", "nan", "none"):
            client_labels = [str(v).strip() for v in df.iloc[0, 1:]]
            data_rows     = df.iloc[1:]
        else:
            client_labels = [f"Client {i+1}" for i in range(df.shape[1] - 1)]
            data_rows     = df

        n    = len(client_labels)
        raws = [{} for _ in range(n)]

        for _, row in data_rows.iterrows():
            label = str(row.iloc[0]).strip()
            if not label or label.lower() in ("nan", "none"):
                continue
            for i, cell in enumerate(row.iloc[1:]):
                if i >= n:
                    break
                v = str(cell).strip()
                if v and v.lower() not in ("nan", "none"):
                    raws[i][label] = v
                elif i > 0 and label not in raws[i] and label in raws[0]:
                    raws[i][label] = raws[0][label]

        result = []
        for i, raw in enumerate(raws):
            if raw:
                norm = _normalize_fields(raw)
                norm["__client_label__"] = client_labels[i] if i < len(client_labels) else f"Client {i+1}"
                result.append(norm)
        return result


def _full_name(c: dict) -> str:
    parts = [c.get("First Name",""), c.get("Middle Initial",""), c.get("Last Name","")]
    return " ".join(p for p in parts if p).strip()


def _do_register(intake: dict):
    bene_parts = []
    for i in ("1", "2"):
        name = intake.get(f"Beneficiary {i} Name", "")
        if name:
            rel = intake.get(f"Beneficiary {i} Rel", "")
            pct = intake.get(f"Beneficiary {i} Pct", "")
            bene_parts.append(f"{name} ({rel}) {pct}%")
    # Co-owner / joint account holder
    co_owner = intake.get("Co-Account Holder Name", "")
    if co_owner:
        bene_parts.append(f"Co-Account Holder: {co_owner}, DOB {intake.get('Co-Account Holder DOB','')}")
    child_idx = 1
    while f"Child {child_idx} Name" in intake:
        cn  = intake[f"Child {child_idx} Name"]
        dob = intake.get(f"Child {child_idx} DOB", "")
        bene_parts.append(f"Child {child_idx}: {cn}" + (f", DOB {dob}" if dob else ""))
        child_idx += 1

    sf_result = json.loads(create_salesforce_contact(
        first_name         = intake.get("First Name", ""),
        last_name          = intake.get("Last Name", ""),
        email              = intake.get("Email", ""),
        phone              = intake.get("Phone", ""),
        date_of_birth      = intake.get("Date of Birth", ""),
        mailing_street     = intake.get("Address", ""),
        mailing_city       = intake.get("City", ""),
        mailing_state      = intake.get("State", ""),
        mailing_zip        = intake.get("ZIP", ""),
        annual_income      = intake.get("Annual Income", ""),
        employer           = intake.get("Employer", ""),
        occupation         = intake.get("Occupation", ""),
        risk_tolerance     = intake.get("Risk Tolerance", ""),
        investment_goal    = intake.get("Investment Goal", ""),
        time_horizon_years = intake.get("Time Horizon (yrs)", ""),
        net_worth          = intake.get("Est. Net Worth", ""),
        liquid_assets      = intake.get("Liquid Assets", ""),
        lead_source        = intake.get("Referral Source", ""),
        notes              = "  |  ".join(bene_parts),
    ))

    sf_id     = sf_result.get("id", "")
    sf_record = MockSalesforce._records.get(sf_id, {})
    return sf_result, sf_record, bene_parts


# ─────────────────────────────────────────────────────────────────────────────
# Client / data lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_client_sheets(client_name: str):
    raw = json.loads(find_client_file(client_name))
    if not raw.get("found"):
        avail = raw.get("available", [])
        msg   = "Client not found."
        if avail:
            msg += f"  Available: {', '.join(avail)}"
        return False, msg, {}
    file_path = raw["path"]
    data = {sheet: json.loads(read_excel_sheet(file_path, sheet)) for sheet in raw["sheets"]}
    return True, file_path, data


def _available_excel_clients() -> list:
    if not CLIENTS_DIR.exists():
        return []
    return [f.stem.replace("_", " ").title() for f in sorted(CLIENTS_DIR.glob("*.xlsx"))]


def _client_has_excel(name: str) -> bool:
    return name.lower() in {n.lower() for n in _available_excel_clients()}


def _all_known_clients() -> list:
    seen, names = set(), []
    for n in _registry_names() + _available_excel_clients():
        if n.lower() not in seen:
            seen.add(n.lower())
            names.append(n)
    return sorted(names)


def _registered_without_data() -> list:
    excel_lower = {n.lower() for n in _available_excel_clients()}
    return [n for n in _registry_names() if n.lower() not in excel_lower]


def _name_to_filename(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name.lower()).strip("_") + ".xlsx"


def _save_account_data(name: str, file_bytes: bytes) -> Path:
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = CLIENTS_DIR / _name_to_filename(name)
    dest.write_bytes(file_bytes)
    return dest


def _data_ready() -> bool:
    return (DATA_DIR / "client_intake.xlsx").exists()


# ─────────────────────────────────────────────────────────────────────────────
# Client context builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_client_context(name: str) -> str:
    lines = [f"CLIENT: {name}", ""]
    entry = _registry_entry(name)
    if entry:
        intake = entry.get("intake", {})
        lines.append("=== REGISTRATION PROFILE ===")
        skip = {"Notes", "WAS", "Fee"}
        for k, v in intake.items():
            if k.startswith("__") or k in skip or not v:
                continue
            lines.append(f"  {k}: {v}")
        if intake.get("Notes"):
            lines.append(f"  Notes / Instructions: {intake['Notes']}")
        if intake.get("Fee"):
            lines.append(f"  Fee Structure (internal): {intake['Fee']}")
        if intake.get("WAS"):
            lines.append(f"  WAS (internal): {intake['WAS']}")
        reg_at = entry.get("registered_at", "")
        if reg_at:
            lines.append(f"  Registration Date: {reg_at[:10]}")
        lines.append("")

    found, _, data = _load_client_sheets(name)
    if found:
        for sheet, rows in data.items():
            if not rows:
                continue
            lines.append(f"=== {sheet.upper()} ===")
            headers = list(rows[0].keys())
            lines.append("  " + " | ".join(headers))
            for row in rows:
                lines.append("  " + " | ".join(str(row.get(h, "")) for h in headers))
            lines.append("")
    else:
        lines.append("=== ACCOUNT DATA ===")
        lines.append("  No Excel account file on record for this client.")
        lines.append("  Analysis is limited to registration profile above.")
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Elite AI Advisor system prompt (Marcus Reid)
# ─────────────────────────────────────────────────────────────────────────────

def _build_advisor_system_prompt(client_name: str, context: str) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    return f"""You are Marcus Reid — a fiduciary wealth management advisor with 30 years of \
private client experience at top-tier RIA firms. You have managed portfolios through \
multiple market cycles, advised clients through business sales, divorces, inheritances, \
and retirement transitions. You serve as the most trusted senior colleague of the financial \
advisor you're speaking with. You are not a chatbot — you are the senior partner they call \
before every important meeting.

Firm: {BRAND} | {PRODUCT}
Today: {today}
Client: {client_name}

━━━ MANDATORY RESPONSE STRUCTURE ━━━
Every single response must include these sections in this order:

**EXECUTIVE SUMMARY**
(1-2 sentences: the single most important thing for the advisor to know right now)

**DIRECT ANSWER**
(Specific, data-driven answer to the exact question asked — cite exact dollar amounts and
percentages from the data. Never round unless the data is unavailable.)

**PROACTIVE INSIGHTS**
(2-4 bullet points of things the advisor needs to know that they didn't ask about —
risks, opportunities, anomalies, time-sensitive items, or items that could embarrass
the advisor if they came up in the meeting unprepared)

**RECOMMENDED ACTIONS**
(Numbered list of specific next steps, ranked by urgency. Each action should include
what to do, why it matters, and ideally the dollar impact or risk magnitude.)

━━━ YOUR ANALYSIS FRAMEWORK ━━━
Apply all of these lenses to every client, even when not asked:
• PORTFOLIO — Allocation drift vs. targets, concentration risk, diversification quality
• TAX — Harvesting opportunities, gain/loss netting, year-end moves, RMD compliance, \
  ordinary vs. qualified income breakdown
• CASH FLOW — Contribution sustainability, distribution pace vs. portfolio longevity, \
  emergency reserves
• RISK — Sequence-of-returns exposure, single-stock concentration, correlation during stress
• ESTATE — Beneficiary designations (current? contingent designated?), account titling, \
  tax-efficient transfer strategies
• GOALS — Is the actual portfolio positioned to achieve what this client said they want?
• LIFE STAGE — Age-appropriate risk posture, upcoming liquidity needs, protection gaps

━━━ COMMUNICATION STANDARDS ━━━
• SPECIFIC: Always cite exact dollar figures and percentages — never use ranges when data exists
• DIRECT: No hedging. Say "rebalance equities by $X" not "you may want to consider rebalancing"
• PRIORITIZED: Lead with what is most urgent and has the greatest dollar impact
• FIDUCIARY: Every recommendation is in the client's best long-term interest
• EXPERIENCED: Write as someone who has navigated this exact situation dozens of times
• MEETING-READY: When relevant, give the advisor the actual words to say to the client

If account data is missing, say so clearly in one sentence, then give the best analysis
possible from the profile data available. Never invent data.

━━━ CLIENT DATA ━━━
<client_context>
{context}
</client_context>"""


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding AI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _onboarding_ai_analyze(intake_text: str) -> str:
    """Ask Claude to extract account types, funding paths, and form recommendations."""
    if not HAS_API_KEY:
        return json.dumps({
            "account_holders": ["Primary Holder"],
            "account_types": ["Individual"],
            "funding_path": "Add Advisor to Existing Fidelity Account",
            "recommended_forms": ["IWSPersonalApp", "AddRemoveAdvisor"],
            "notes": "Mock mode — real analysis requires ANTHROPIC_API_KEY",
        })
    prompt = f"""You are a wealth management operations specialist. Analyze this client intake data and return a JSON object with:
- "account_holders": list of full names of account holders
- "account_types": list of account types needed (e.g. ["Individual", "Joint Brokerage", "Traditional IRA", "Trust"])
- "funding_path": one of "Add Advisor to Existing Account", "Internal Transfer (Journal Request)", "External Transfer", "New Money"
- "recommended_forms": list of form keys from: IWSPersonalApp, IWSTrustApp, AddRemoveAdvisor, JournalRequest
- "notes": any important observations about the onboarding

INTAKE DATA:
{intake_text}

Return ONLY valid JSON, no markdown, no explanation."""
    client_api = anthropic.Anthropic()
    try:
        resp = client_api.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _onboarding_ai_prefill(form_key: str, intake_data: dict, holders: list) -> str:
    """Generate a pre-fill preview for a given form using intake data."""
    form = FORM_CATALOG.get(form_key, {})
    fields = form.get("fields", [])
    if not HAS_API_KEY:
        # Simple mock mapping
        mock = {}
        for f in fields:
            fl = f.lower()
            if "holder 1" in fl or ("account holder" in fl and "2" not in fl):
                mock[f] = holders[0] if holders else "—"
            elif "holder 2" in fl:
                mock[f] = holders[1] if len(holders) > 1 else "—"
            elif "address" in fl:
                mock[f] = intake_data.get("Address", "—")
            elif "city" in fl:
                mock[f] = intake_data.get("City", "—")
            elif "state" in fl:
                mock[f] = intake_data.get("State", "—")
            elif "zip" in fl:
                mock[f] = intake_data.get("ZIP", "—")
            elif "email" in fl:
                mock[f] = intake_data.get("Email", "—")
            elif "phone" in fl:
                mock[f] = intake_data.get("Phone", "—")
            else:
                mock[f] = "—"
        return json.dumps(mock, indent=2)

    prompt = f"""Map the following client intake data to this form's fields.
Return a JSON object where keys are the exact field names listed and values are what should be pre-filled from the intake data (or "—" if not available).

FORM: {form.get('label','')}
FIELDS TO FILL: {json.dumps(fields)}
ACCOUNT HOLDERS: {json.dumps(holders)}
INTAKE DATA: {json.dumps(intake_data, indent=2)}

Return ONLY valid JSON, no markdown."""
    client_api = anthropic.Anthropic()
    try:
        resp = client_api.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
<div style="padding:0.5rem 0 1.1rem;text-align:center;
     border-bottom:1px solid rgba(0,212,255,0.1);margin-bottom:1rem;">
  <div style="color:#00D4FF;font-size:1rem;font-weight:800;letter-spacing:0.04em;
       text-shadow:0 0 12px rgba(0,212,255,0.5);">⬡ {BRAND}</div>
  <div style="color:#1E3A5F;font-size:0.58rem;letter-spacing:0.14em;
       margin-top:3px;text-transform:uppercase;">{PRODUCT}</div>
</div>
""", unsafe_allow_html=True)

    if HAS_API_KEY:
        st.markdown(
            '<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);'
            'border-radius:6px;padding:5px 10px;font-size:0.73rem;color:#10B981;'
            'text-align:center;margin-bottom:0.5rem;">🟢 Live AI Mode</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);'
            'border-radius:6px;padding:5px 10px;font-size:0.73rem;color:#F59E0B;'
            'text-align:center;margin-bottom:0.5rem;">🟡 Mock Mode — no API key</div>',
            unsafe_allow_html=True,
        )
    st.divider()

    st.markdown(
        '<div style="color:#1E3A5F;font-size:0.6rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.12em;margin-bottom:0.4rem;">Navigation</div>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "nav",
        ["Register Client", "Meeting Prep", "AI Advisor", "Client Onboarding"],
        label_visibility="collapsed",
    )
    st.divider()

    if st.button("⚙  Generate Sample Data", use_container_width=True):
        with st.spinner("Creating sample files…"):
            create_dummy_data()
        st.success("Sample data created.")
        st.rerun()

    st.divider()
    if _data_ready():
        st.caption(f"✅ Data: `{DATA_DIR}/`")
    else:
        st.caption("⚠ No data — click Generate above")

    all_clients = _all_known_clients()
    if all_clients:
        st.markdown(
            '<div style="color:#1E3A5F;font-size:0.6rem;font-weight:700;'
            'text-transform:uppercase;letter-spacing:0.1em;margin:0.5rem 0 0.3rem;">'
            'Known Clients</div>',
            unsafe_allow_html=True,
        )
        for cn in all_clients:
            has_xl  = _client_has_excel(cn)
            dot_col = "#00D4FF" if has_xl else "#1E3A5F"
            st.markdown(
                f'<div style="font-size:0.77rem;color:#334155;padding:1px 0;">'
                f'<span style="color:{dot_col};">●</span> {cn}</div>',
                unsafe_allow_html=True,
            )

    # ── Persistent AI Assistant ───────────────────────────────────────────────
    st.divider()
    st.markdown(
        '<div style="color:#00D4FF;font-size:0.62rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.12em;margin-bottom:0.5rem;">'
        '🤖 AI Assistant</div>',
        unsafe_allow_html=True,
    )

    # Determine context: use whichever client is currently active
    _sb_ctx_client = (
        st.session_state.get("aac_client")
        or st.session_state.get("mp_client")
        or st.session_state.get("ob_client_sel")
    )
    if _sb_ctx_client and _all_known_clients():
        st.markdown(
            f'<div style="font-size:0.7rem;color:#334155;margin-bottom:0.4rem;">'
            f'Context: <span style="color:#94A3B8;">{_sb_ctx_client}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:0.7rem;color:#334155;margin-bottom:0.4rem;">'
            'General mode — no client selected</div>',
            unsafe_allow_html=True,
        )

    st.session_state.setdefault("sb_history", [])

    # Show last exchange inline
    if st.session_state["sb_history"]:
        last = st.session_state["sb_history"][-1]
        st.markdown(
            f'<div style="background:rgba(0,212,255,0.04);border:1px solid rgba(0,212,255,0.1);'
            f'border-radius:7px;padding:0.5rem 0.65rem;margin-bottom:0.4rem;'
            f'font-size:0.75rem;color:#94A3B8;max-height:160px;overflow-y:auto;">'
            f'<span style="color:#475569;font-size:0.65rem;">YOU:</span><br>'
            f'{last["q"]}<br><br>'
            f'<span style="color:#475569;font-size:0.65rem;">MARCUS:</span><br>'
            f'<span style="color:#CBD5E1;">{last["a"][:400]}{"…" if len(last["a"])>400 else ""}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Input form (forms work in sidebar; avoids page re-run on every keystroke)
    with st.form(key="sb_ai_form", clear_on_submit=True):
        sb_q = st.text_input(
            "Ask anything…",
            placeholder="e.g. What forms do I need for a joint account?",
            label_visibility="collapsed",
        )
        col_send, col_clr = st.columns([3, 1])
        with col_send:
            sb_submitted = st.form_submit_button("Ask →", use_container_width=True)
        with col_clr:
            sb_clear = st.form_submit_button("✕", use_container_width=True)

    if sb_clear:
        st.session_state["sb_history"] = []
        st.rerun()

    if sb_submitted and sb_q.strip():
        q = sb_q.strip()
        if HAS_API_KEY:
            # Build context: client data if available, otherwise general
            if _sb_ctx_client:
                _sb_context = _build_client_context(_sb_ctx_client)
                _sb_system  = _build_advisor_system_prompt(_sb_ctx_client, _sb_context)
            else:
                _sb_system = (
                    f"You are Marcus Reid, a senior wealth management advisor at {BRAND}. "
                    "Answer questions about wealth management processes, onboarding, compliance, "
                    "forms, and general advisory best practices. Be direct and concise."
                )
            # Build message history for context
            _sb_msgs = []
            for _h in st.session_state["sb_history"][-6:]:
                _sb_msgs.append({"role": "user",      "content": _h["q"]})
                _sb_msgs.append({"role": "assistant",  "content": _h["a"]})
            _sb_msgs.append({"role": "user", "content": q})
            try:
                _sb_resp = anthropic.Anthropic().messages.create(
                    model="claude-opus-4-6",
                    max_tokens=1024,
                    system=_sb_system,
                    messages=_sb_msgs,
                )
                answer = _sb_resp.content[0].text
            except Exception as exc:
                answer = f"⚠ Error: {exc}"
        else:
            answer = (
                "*(Mock mode — add ANTHROPIC_API_KEY for live responses)*\n\n"
                "I'm Marcus Reid, your AI wealth advisor. I can help with client analysis, "
                "onboarding processes, form selection, meeting prep, and more."
            )
        st.session_state["sb_history"].append({"q": q, "a": answer})
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Page — Register Client
# ─────────────────────────────────────────────────────────────────────────────

if page == "Register Client":
    _html_page_header(
        "Register New Client",
        "Parse an Excel intake form and create a Salesforce CRM record. "
        "The client is instantly available across all platform features.",
        "📋",
    )

    col_l, col_r = st.columns([1, 2])
    with col_l:
        source_choice = st.radio("Intake form source", ["Use sample form", "Upload my own"])

    intake_source = None
    with col_r:
        if source_choice == "Use sample form":
            if st.session_state.get("_last_source") != "sample":
                st.session_state.pop("parsed_clients", None)
                st.session_state["_last_source"] = "sample"
            default_path = DATA_DIR / "client_intake.xlsx"
            if default_path.exists():
                intake_source = default_path
                st.info(f"📄 `{default_path.name}`")
            else:
                st.warning("Sample data not found — click **Generate Sample Data** in the sidebar first.")
        else:
            uploaded = st.file_uploader("Upload intake form (.xlsx)", type=["xlsx"])
            if uploaded:
                file_key = f"{uploaded.name}:{uploaded.size}"
                if st.session_state.get("_last_source") != file_key:
                    st.session_state.pop("parsed_clients", None)
                    st.session_state["_last_source"] = file_key
                intake_source = uploaded

    if intake_source is not None and "parsed_clients" not in st.session_state:
        try:
            clients_parsed = _read_intake_form(intake_source)
            if not clients_parsed:
                st.error("Could not parse intake form — no data rows found.")
            else:
                st.session_state["parsed_clients"] = clients_parsed
        except Exception as exc:
            st.error(f"Failed to read file: {exc}")

    if intake_source is None:
        st.session_state.pop("parsed_clients", None)
        st.session_state.pop("reg_result", None)

    parsed_clients  = st.session_state.get("parsed_clients", [])
    selected_intake = None

    if len(parsed_clients) >= 2:
        # ── Joint / multi-party form: both are primary account holders ──────
        holder1 = dict(parsed_clients[0])
        holder2 = parsed_clients[1]
        # Store co-owner info on the primary record (for CRM notes)
        holder1["Co-Account Holder Name"] = _full_name(holder2)
        holder1["Co-Account Holder DOB"]  = holder2.get("Date of Birth", "")
        # Additional parties beyond 2 treated as children
        children = parsed_clients[2:]
        for idx, child in enumerate(children, start=1):
            holder1[f"Child {idx} Name"] = _full_name(child)
            holder1[f"Child {idx} DOB"]  = child.get("Date of Birth", "")
        selected_intake = holder1
        # Display both as primary account holders
        name1 = _full_name(holder1)
        name2 = holder1["Co-Account Holder Name"]
        st.info(
            f"👥 **Account Holder 1:** {name1}   |   **Account Holder 2:** {name2}"
            + (f"   |   **Additional:** {', '.join(_full_name(c) for c in children)}" if children else "")
        )
    elif len(parsed_clients) == 1:
        selected_intake = parsed_clients[0]

    if st.button("▶  Register Client", type="primary", disabled=selected_intake is None):
        st.session_state.pop("reg_result", None)
        intake = selected_intake

        with st.status("Registering client…", expanded=True) as status_box:
            client_full = f"{intake.get('First Name','')} {intake.get('Last Name','')}".strip()
            field_count = sum(1 for k, v in intake.items() if not k.startswith("__") and v)
            st.write(f"✅ Parsed **{field_count} fields** for **{client_full}**")
            st.write("☁️  Creating Salesforce record…")
            sf_result, sf_record, bene_parts = _do_register(intake)

            if sf_result.get("success"):
                sf_id = sf_result["id"]
                st.write(f"✅ Salesforce ID: `{sf_id}`")
                st.write("💾 Saving to unified client registry…")
                _save_to_registry(client_full, sf_id, intake, sf_record)
                st.write(f"✅ **{client_full}** is now available in Meeting Prep and AI Advisor")
                status_box.update(label="Registration complete!", state="complete")
                st.session_state["reg_result"] = {
                    "intake":     intake,
                    "sf_result":  sf_result,
                    "sf_record":  sf_record,
                    "bene_parts": bene_parts,
                    "name":       client_full,
                }
            else:
                status_box.update(label="Salesforce error", state="error")
                st.error(json.dumps(sf_result, indent=2))
                st.stop()

    if "reg_result" in st.session_state:
        res    = st.session_state["reg_result"]
        intake = res["intake"]
        sf_rec = res["sf_record"]
        sf_id  = res["sf_result"]["id"]
        name   = res["name"]
        benes  = res["bene_parts"]

        st.success(f"✅  **{name}** registered — Salesforce ID: `{sf_id}`")
        st.markdown("")

        _html_stat_row([
            ("Annual Income",  _fmt_money(intake.get("Annual Income",  0))),
            ("Net Worth",      _fmt_money(intake.get("Est. Net Worth", 0))),
            ("Liquid Assets",  _fmt_money(intake.get("Liquid Assets",  0))),
            ("Time Horizon",   f"{intake.get('Time Horizon (yrs)', '—')} yrs"),
        ])
        st.markdown("")

        cl, cr = st.columns(2)
        with cl:
            _html_section_header("Personal Details", "👤")
            addr = " ".join(filter(None, [
                intake.get("Address",""), intake.get("City",""),
                intake.get("State",""), intake.get("ZIP",""),
            ]))
            rows = [
                ("Name",         name),
                ("Date of Birth", intake.get("Date of Birth","—")),
                ("Email",        intake.get("Email","—")),
                ("Phone",        intake.get("Phone","—")),
                ("Address",      addr or "—"),
                ("Employer",     intake.get("Employer","—")),
                ("Occupation",   intake.get("Occupation","—")),
                ("Lead Source",  intake.get("Referral Source","—")),
            ]
            # Show co-account holder if present (joint account)
            if intake.get("Co-Account Holder Name"):
                rows.append(("Co-Account Holder",     intake["Co-Account Holder Name"]))
            if intake.get("Co-Account Holder DOB"):
                rows.append(("Co-Account Holder DOB", intake["Co-Account Holder DOB"]))
            ci = 1
            while f"Child {ci} Name" in intake:
                dob = intake.get(f"Child {ci} DOB","")
                rows.append((f"Child {ci}", intake[f"Child {ci} Name"] + (f" (DOB: {dob})" if dob else "")))
                ci += 1
            for label, val in rows:
                st.markdown(f"**{label}:** {val}")

        with cr:
            _html_section_header("Financial Profile", "💰")
            for label, val in [
                ("Risk Tolerance",  intake.get("Risk Tolerance","—")),
                ("Investment Goal", intake.get("Investment Goal","—")),
                ("Annual Income",   _fmt_money(intake.get("Annual Income",0))),
                ("Net Worth",       _fmt_money(intake.get("Est. Net Worth",0))),
                ("Liquid Assets",   _fmt_money(intake.get("Liquid Assets",0))),
                ("Time Horizon",    f"{intake.get('Time Horizon (yrs)','—')} years"),
            ]:
                st.markdown(f"**{label}:** {val}")

        if benes:
            st.divider()
            _html_section_header("Household / Beneficiaries", "👨‍👩‍👧")
            for b in benes:
                st.markdown(f"• {b}")

        st.divider()
        with st.expander("📦 Raw Salesforce Record"):
            st.json(sf_rec)

    _html_footer()


# ─────────────────────────────────────────────────────────────────────────────
# Page — Meeting Prep
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Meeting Prep":
    _html_page_header(
        "Meeting Prep",
        "Instant advisor brief for any registered client — account analysis, allocation, "
        "tax summary, and talking points.",
        "📊",
    )

    all_clients = _all_known_clients()
    no_data     = _registered_without_data()

    col_a, col_b = st.columns([2, 1])
    with col_a:
        if all_clients:
            options      = all_clients + ["— Enter name manually —"]
            saved_client = st.session_state.get("mp_client", "")
            default_idx  = all_clients.index(saved_client) if saved_client in all_clients else 0
            chosen = st.selectbox("Select client", options, index=default_idx)
            client_name = st.text_input("Client name", placeholder="e.g. Robert Thornton") \
                if chosen == "— Enter name manually —" else chosen
        else:
            client_name = st.text_input(
                "Client name",
                placeholder="e.g. Robert Thornton",
                value=st.session_state.get("mp_client",""),
            )

    with col_b:
        excel_clients = _available_excel_clients()
        if excel_clients:
            st.markdown("**Full data available:**")
            for c in excel_clients:
                st.markdown(f"• {c}")
        if no_data:
            st.markdown("**Profile only:**")
            for c in no_data:
                st.markdown(f"• {c}")
        if not all_clients:
            st.caption("No clients yet. Register one or generate sample data.")

    if no_data:
        with st.expander(
            f"📤 Upload account data — "
            f"{len(no_data)} client{'s' if len(no_data)!=1 else ''} missing Excel data"
        ):
            st.caption("Upload an account workbook to unlock full Meeting Prep and deeper AI analysis.")
            upload_target = st.selectbox("Client", no_data, key="mp_upload_target")
            upload_file   = st.file_uploader(
                f"Account workbook (.xlsx) for {upload_target}",
                type=["xlsx"], key="mp_upload_file",
            )
            if upload_file:
                if st.button("💾 Save account data", key="mp_save_btn", type="primary"):
                    _save_account_data(upload_target, upload_file.read())
                    st.success(f"✅ Saved — {upload_target} now has full account data.")
                    st.rerun()

    st.markdown("")
    can_run = bool(client_name.strip())
    if st.button("▶  Generate Brief", type="primary", disabled=not can_run):
        st.session_state["mp_client"] = client_name.strip()
        st.session_state.pop("mp_result", None)

        with st.status(f"Preparing brief for {client_name.strip()}…", expanded=True) as sb:
            has_xl = _client_has_excel(client_name.strip())
            reg    = _registry_entry(client_name.strip())

            if has_xl:
                st.write("🔍 Loading account data…")
                found, detail, data = _load_client_sheets(client_name.strip())
                if not found:
                    sb.update(label="Data not found", state="error")
                    st.error(detail)
                    st.stop()
                st.write(f"✅ Found: `{detail}`")
                for sheet in data:
                    st.write(f"📋 Sheet loaded: **{sheet}**")
                sb.update(label="Brief ready!", state="complete")
                st.session_state["mp_result"] = {
                    "mode": "excel", "data": data, "client": client_name.strip(), "reg": reg,
                }
            elif reg:
                st.write("📋 Loading registration profile…")
                sb.update(label="Profile brief ready!", state="complete")
                st.session_state["mp_result"] = {
                    "mode": "profile", "data": {}, "client": client_name.strip(), "reg": reg,
                }
            else:
                sb.update(label="Client not found", state="error")
                st.error(
                    f"'{client_name.strip()}' is not registered and has no account data. "
                    "Register the client first."
                )
                st.stop()

    if "mp_result" in st.session_state:
        mp          = st.session_state["mp_result"]
        client_name = mp["client"]
        mode        = mp["mode"]
        data        = mp["data"]
        reg         = mp["reg"]
        intake      = (reg or {}).get("intake", {})

        has_xl = (mode == "excel")
        _html_client_badge(client_name, has_excel=has_xl, has_registry=bool(reg))
        st.markdown(f"**Prepared:** {datetime.now().strftime('%B %d, %Y  ·  %-I:%M %p')}")
        st.markdown("")

        if mode == "excel":
            acct_rows  = data.get("Account Summary",              [])
            dc_rows    = data.get("Distributions & Contributions", [])
            tax_rows   = data.get("Tax & Realized GL",            [])
            bene_rows  = data.get("Beneficiaries",                [])
            alloc_rows = data.get("Allocation",                   [])

            total_aum     = sum(_safe_float(r.get("Market Value",0)) for r in acct_rows)
            total_contrib = sum(_safe_float(r.get("Amount ($)",0)) for r in dc_rows if _safe_float(r.get("Amount ($)",0)) > 0)
            total_distrib = sum(_safe_float(r.get("Amount ($)",0)) for r in dc_rows if _safe_float(r.get("Amount ($)",0)) < 0)
            net_activity  = total_contrib + total_distrib
            tax_map       = {r.get("Category","").strip(): _safe_float(r.get("Amount ($)",0)) for r in tax_rows}
            est_taxes     = sum(v for k,v in tax_map.items() if "Est. Tax" in k)
            net_gl        = sum(v for k,v in tax_map.items() if "Realized" in k)
            qual_div      = tax_map.get("Qualified Dividends", 0.0)
            nq_div        = tax_map.get("Non-Qual Dividends",  0.0)
            interest      = tax_map.get("Interest Income",     0.0)
            total_inc     = qual_div + nq_div + interest
            drift_flags   = []
            for row in alloc_rows:
                try:
                    dval = float(str(row.get("Drift","0")).replace("%","").replace("+",""))
                    if abs(dval) >= 2.0:
                        drift_flags.append((row.get("Asset Class",""), row.get("Drift",""), dval))
                except (ValueError, AttributeError):
                    pass
            rmd_rows = [r for r in dc_rows if "RMD" in r.get("Description","")]

            _html_stat_row([
                ("Total AUM",           _fmt_money(total_aum)),
                ("Net Activity (YTD)",  _fmt_money(net_activity)),
                ("Net Realized G/L",    _fmt_money(net_gl)),
                ("Est. Tax Paid (YTD)", _fmt_money(est_taxes)),
            ])
            st.markdown("")

            _html_section_header("Account Summary", "🏦")
            if acct_rows:
                df_a = pd.DataFrame(acct_rows)
                if "Market Value" in df_a.columns:
                    df_a["Market Value"] = df_a["Market Value"].apply(_fmt_money)
                st.dataframe(df_a, use_container_width=True, hide_index=True)
                st.caption(f"Total AUM: **{_fmt_money(total_aum)}** across {len(acct_rows)} accounts")

            _html_section_header("Distributions & Contributions (YTD)", "💸")
            if dc_rows:
                df_dc = pd.DataFrame(dc_rows)
                if "Amount ($)" in df_dc.columns:
                    df_dc["Amount ($)"] = df_dc["Amount ($)"].apply(_fmt_money)
                st.dataframe(df_dc, use_container_width=True, hide_index=True)
                _html_stat_row([
                    ("Contributions", _fmt_money(total_contrib)),
                    ("Distributions", _fmt_money(total_distrib)),
                    ("Net Activity",  _fmt_money(net_activity)),
                ])

            _html_section_header("Tax Summary (YTD)", "🧾")
            if tax_rows:
                tc1, tc2 = st.columns(2)
                with tc1:
                    st.markdown("**Realized Gains / Losses**")
                    for lbl, amt in [
                        ("ST Gains",  tax_map.get("Realized ST Gains",0)),
                        ("LT Gains",  tax_map.get("Realized LT Gains",0)),
                        ("ST Losses", tax_map.get("Realized ST Losses",0)),
                        ("LT Losses", tax_map.get("Realized LT Losses",0)),
                    ]:
                        st.markdown(f"**{lbl}:** {_fmt_money(amt)}")
                    st.markdown(f"**Net Realized G/L:** {_fmt_money(net_gl)}")
                    st.markdown(f"**Est. Tax Paid:** {_fmt_money(est_taxes)}")
                with tc2:
                    st.markdown("**Investment Income**")
                    for lbl, amt in [
                        ("Qualified Dividends", qual_div),
                        ("Non-Qual Dividends",  nq_div),
                        ("Interest Income",     interest),
                    ]:
                        st.markdown(f"**{lbl}:** {_fmt_money(amt)}")
                    st.markdown(f"**Total Income:** {_fmt_money(total_inc)}")

            _html_section_header("Beneficiaries", "👨‍👩‍👧")
            if bene_rows:
                df_b = pd.DataFrame(bene_rows)
                if "Pct" in df_b.columns:
                    df_b["Pct"] = df_b["Pct"].apply(lambda v: f"{v}%")
                st.dataframe(df_b, use_container_width=True, hide_index=True)

            _html_section_header("Allocation vs. Target", "📈")
            if alloc_rows:
                df_al = pd.DataFrame(alloc_rows)
                if "Market Value" in df_al.columns:
                    df_al["Market Value"] = df_al["Market Value"].apply(_fmt_money)
                def _flag(v):
                    try:
                        dval = float(str(v).replace("%","").replace("+",""))
                        return f"{v} ◄" if abs(dval) >= 2.0 else str(v)
                    except (ValueError, TypeError):
                        return str(v)
                if "Drift" in df_al.columns:
                    df_al["Drift"] = df_al["Drift"].apply(_flag)
                st.dataframe(df_al, use_container_width=True, hide_index=True)
                if drift_flags:
                    st.caption("◄ = exceeds ±2% rebalancing threshold")

            _html_section_header("Advisor Talking Points", "💬")
            has_pts = False
            for ac, drift, dval in sorted(drift_flags, key=lambda x: abs(x[2]), reverse=True):
                _html_callout(
                    f"<strong>Rebalancing — {ac}:</strong> {drift} "
                    f"({'OVERWEIGHT' if dval > 0 else 'UNDERWEIGHT'}). Review rebalancing trade.",
                    "warning",
                )
                has_pts = True
            for row in rmd_rows:
                amt = _safe_float(row.get("Amount ($)",0))
                _html_callout(
                    f"<strong>RMD:</strong> {_fmt_money(abs(amt))} taken {row.get('Date','')} "
                    f"from {row.get('Account','')}. Confirm tax withholding election on file.",
                    "info",
                )
                has_pts = True
            if tax_rows:
                if net_gl > 0:
                    _html_callout(
                        f"<strong>Tax Coordination:</strong> Net realized gain of {_fmt_money(net_gl)} "
                        "YTD. Coordinate with CPA before year-end for offset opportunities.",
                        "warning",
                    )
                else:
                    _html_callout(
                        f"<strong>Tax-Loss Harvesting:</strong> Net realized loss of "
                        f"{_fmt_money(abs(net_gl))} YTD. Assess additional TLH opportunities.",
                        "info",
                    )
                has_pts = True
            if acct_rows:
                _html_callout(
                    f"<strong>Portfolio Review:</strong> {_fmt_money(total_aum)} across "
                    f"{len(acct_rows)} accounts. Review consolidation opportunities.",
                    "info",
                )
                has_pts = True
            if not has_pts:
                st.markdown("_No flags detected._")

            st.divider()
            with st.expander("📄 Full Text One-Pager (copy / print ready)"):
                st.code(_build_one_pager(client_name, data), language=None)

        else:
            _html_callout(
                "This client has a registration profile but no account data on file. "
                "Upload an Excel workbook above to unlock the full briefing.",
                "warning",
            )
            st.markdown("")

            income   = intake.get("Annual Income","")
            networth = intake.get("Est. Net Worth","")
            liquid   = intake.get("Liquid Assets","")
            horizon  = intake.get("Time Horizon (yrs)","—")

            _html_stat_row([
                ("Annual Income",   _fmt_money(income) if income else "—"),
                ("Est. Net Worth",  _fmt_money(networth) if networth else "—"),
                ("Liquid Assets",   _fmt_money(liquid) if liquid else "—"),
                ("Time Horizon",    f"{horizon} yrs"),
            ])
            st.markdown("")

            cl, cr = st.columns(2)
            with cl:
                _html_section_header("Personal Details", "👤")
                addr = " ".join(filter(None, [
                    intake.get("Address",""), intake.get("City",""),
                    intake.get("State",""), intake.get("ZIP",""),
                ]))
                for lbl, val in [
                    ("Date of Birth", intake.get("Date of Birth","—")),
                    ("Email",        intake.get("Email","—")),
                    ("Phone",        intake.get("Phone","—")),
                    ("Address",      addr or "—"),
                    ("Employer",     intake.get("Employer","—")),
                    ("Occupation",   intake.get("Occupation","—")),
                    ("Lead Source",  intake.get("Referral Source","—")),
                ]:
                    st.markdown(f"**{lbl}:** {val}")
                if intake.get("Co-Account Holder Name"):
                    st.markdown(f"**Co-Account Holder:** {intake['Co-Account Holder Name']}")
                ci = 1
                while intake.get(f"Child {ci} Name"):
                    dob = intake.get(f"Child {ci} DOB","")
                    st.markdown(f"**Child {ci}:** {intake[f'Child {ci} Name']}" +
                                (f" (DOB: {dob})" if dob else ""))
                    ci += 1

            with cr:
                _html_section_header("Investment Profile", "💰")
                for lbl, val in [
                    ("Risk Tolerance",  intake.get("Risk Tolerance","—")),
                    ("Investment Goal", intake.get("Investment Goal","—")),
                    ("Time Horizon",    f"{horizon} years"),
                ]:
                    st.markdown(f"**{lbl}:** {val}")
                if intake.get("Notes"):
                    st.markdown("")
                    _html_section_header("Notes / Instructions", "📝")
                    st.markdown(intake["Notes"])

            _html_section_header("Profile-Based Talking Points", "💬")
            if intake.get("Risk Tolerance"):
                _html_callout(
                    f"<strong>Investment Profile:</strong> Risk tolerance is "
                    f"<em>{intake['Risk Tolerance']}</em> with a {horizon}-year horizon. "
                    "Confirm these are still current.",
                    "info",
                )
            missing = [
                f for f in ["Annual Income","Est. Net Worth","Liquid Assets"]
                if not intake.get(f)
            ]
            if missing:
                _html_callout(
                    f"<strong>Missing Financial Data:</strong> {', '.join(missing)} not on file. "
                    "Gather before completing financial plan.",
                    "warning",
                )
            if not _client_has_excel(client_name):
                _html_callout(
                    "<strong>Account Data Required:</strong> Upload this client's account "
                    "workbook to enable allocation review, tax analysis, and full briefing.",
                    "alert",
                )

    _html_footer()


# ─────────────────────────────────────────────────────────────────────────────
# Page — AI Advisor
# ─────────────────────────────────────────────────────────────────────────────

elif page == "AI Advisor":
    _html_page_header(
        "AI Wealth Advisor",
        "Ask any question about a client's portfolio, tax picture, upcoming meeting, "
        "or financial plan. Powered by Claude with full client context.",
        "🤖",
    )

    all_clients = _all_known_clients()
    if not all_clients:
        _html_callout(
            "No clients in the system yet. Register a client or generate sample data from the sidebar.",
            "warning",
        )
        _html_footer()
        st.stop()

    saved_aac   = st.session_state.get("aac_client", all_clients[0])
    default_i   = all_clients.index(saved_aac) if saved_aac in all_clients else 0
    sel_client  = st.selectbox("Select client", all_clients, index=default_i)

    if sel_client != st.session_state.get("aac_client"):
        st.session_state["aac_client"]  = sel_client
        st.session_state["aac_history"] = []
        st.rerun()

    st.session_state.setdefault("aac_history", [])
    history: list = st.session_state["aac_history"]

    reg   = _registry_entry(sel_client)
    xl_ok = _client_has_excel(sel_client)
    _html_client_badge(sel_client, has_excel=xl_ok, has_registry=bool(reg))

    if not reg and not xl_ok:
        _html_callout("No data found for this client. Register them first.", "alert")
        _html_footer()
        st.stop()

    st.markdown(
        '<div style="color:#334155;font-size:0.77rem;margin-bottom:0.75rem;">'
        '💡 <em>Try asking:</em> &nbsp;'
        '"How should I approach this meeting?" &nbsp;·&nbsp; '
        '"What are the red flags?" &nbsp;·&nbsp; '
        '"Walk me through the tax picture" &nbsp;·&nbsp; '
        '"What opportunities am I missing?"'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input(f"Ask about {sel_client}…")

    if question:
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            placeholder = st.empty()

            if HAS_API_KEY:
                context       = _build_client_context(sel_client)
                system_prompt = _build_advisor_system_prompt(sel_client, context)
                api_messages  = [{"role": m["role"], "content": m["content"]}
                                  for m in history[-30:]]
                full_response = ""
                client_api    = anthropic.Anthropic()
                try:
                    with client_api.messages.stream(
                        model      = "claude-opus-4-6",
                        max_tokens = 4096,
                        system     = system_prompt,
                        messages   = api_messages,
                    ) as stream:
                        for text in stream.text_stream:
                            full_response += text
                            placeholder.markdown(full_response + "▌")
                    placeholder.markdown(full_response)
                except Exception as exc:
                    full_response = f"⚠ API error: {exc}"
                    placeholder.markdown(full_response)

            else:
                intake    = (reg or {}).get("intake", {})
                _, _, ex  = _load_client_sheets(sel_client)
                acct_rows = ex.get("Account Summary", [])
                alloc_rows= ex.get("Allocation",      [])
                tax_rows  = ex.get("Tax & Realized GL",[])
                dc_rows   = ex.get("Distributions & Contributions",[])
                total_aum = sum(_safe_float(r.get("Market Value",0)) for r in acct_rows)
                q_lower   = question.lower()

                def _mock_preamble():
                    return (
                        f"**EXECUTIVE SUMMARY**\n"
                        f"{sel_client} has {_fmt_money(total_aum)} AUM across "
                        f"{len(acct_rows)} account(s).\n\n"
                        if acct_rows else
                        f"**EXECUTIVE SUMMARY**\nProfile data available; no account file loaded.\n\n"
                    )

                if any(w in q_lower for w in ("approach","meeting","agenda","prepare","talk")):
                    full_response = (
                        f"{_mock_preamble()}"
                        f"**DIRECT ANSWER — Suggested Meeting Agenda**\n\n"
                        f"1. Personal check-in (5 min)\n"
                        f"2. Portfolio performance review — {_fmt_money(total_aum)} total AUM (10 min)\n"
                        f"3. Allocation review and any rebalancing needed (10 min)\n"
                        f"4. Tax update and year-end planning (10 min)\n"
                        f"5. Goals check — still on track? (10 min)\n"
                        f"6. Any life changes, new needs (5 min)\n\n"
                        f"**PROACTIVE INSIGHTS**\n"
                        f"• Verify beneficiary designations are current\n"
                        f"• Confirm risk tolerance hasn't changed\n"
                        f"• Ask about any planned large expenses or income changes\n\n"
                        f"**RECOMMENDED ACTIONS**\n"
                        f"1. Pull latest account statements before the meeting\n"
                        f"2. Review allocation drift vs. targets\n"
                        f"3. Check any open RMD requirements\n\n"
                        f"*(Mock mode — API key required for full AI analysis)*"
                    )
                elif any(w in q_lower for w in ("aum","total","value","balance","portfolio")):
                    lines = [_mock_preamble(), "**DIRECT ANSWER — Portfolio Value**\n"]
                    for r in acct_rows:
                        lines.append(f"• {r.get('Account','')} ({r.get('Account #','')}): "
                                     f"{_fmt_money(r.get('Market Value',0))}")
                    full_response = "\n".join(lines)
                elif any(w in q_lower for w in ("tax","gain","loss","harvest","rmd")):
                    if tax_rows:
                        tax_map = {r.get("Category","").strip(): _safe_float(r.get("Amount ($)",0)) for r in tax_rows}
                        net_gl  = sum(v for k,v in tax_map.items() if "Realized" in k)
                        taxes   = sum(v for k,v in tax_map.items() if "Est. Tax" in k)
                        full_response = (
                            f"{_mock_preamble()}"
                            f"**DIRECT ANSWER — Tax Picture**\n\n"
                            f"• Net realized G/L: **{_fmt_money(net_gl)}**\n"
                            f"• Estimated taxes paid: **{_fmt_money(taxes)}**\n\n"
                            f"**PROACTIVE INSIGHTS**\n"
                            f"• {'Consider TLH opportunities' if net_gl < 0 else 'Coordinate with CPA on gain offset'}\n\n"
                            f"*(Mock mode)*"
                        )
                    else:
                        full_response = "No tax data on file. Upload account workbook for tax analysis."
                else:
                    full_response = (
                        f"*(Mock mode — live AI requires an ANTHROPIC_API_KEY)*\n\n"
                        f"{_mock_preamble()}"
                        f"**Available Data**\n"
                    )
                    if intake:
                        for f in ("Risk Tolerance","Investment Goal","Annual Income","Est. Net Worth"):
                            if intake.get(f):
                                full_response += f"• {f}: {intake[f]}\n"
                    if acct_rows:
                        full_response += f"\nTotal AUM: **{_fmt_money(total_aum)}** across {len(acct_rows)} accounts.\n"

                placeholder.markdown(full_response)

            history.append({"role": "assistant", "content": full_response})

    if history:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🗑  Clear conversation"):
                st.session_state["aac_history"] = []
                st.rerun()
        with col2:
            turns = len(history) // 2
            st.caption(f"Session: {turns} exchange{'s' if turns != 1 else ''} in memory")

    _html_footer()


# ─────────────────────────────────────────────────────────────────────────────
# Page — Client Onboarding
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Client Onboarding":
    _html_page_header(
        "Client Onboarding Workflow",
        "AI-powered intake extraction → form selection → pre-fill → DocuSign → post-signature checklist.",
        "🚀",
    )

    # ── Session state init ────────────────────────────────────────────────────
    st.session_state.setdefault("ob_step",         0)   # 0=intake,1=forms,2=docusign,3=close
    st.session_state.setdefault("ob_analysis",     None)
    st.session_state.setdefault("ob_selected_forms", [])
    st.session_state.setdefault("ob_prefills",     {})
    st.session_state.setdefault("ob_filled_pdfs",  {})
    st.session_state.setdefault("ob_intake",       {})
    st.session_state.setdefault("ob_holders",      [])
    st.session_state.setdefault("ob_envelope_sent", False)
    st.session_state.setdefault("ob_post_checks",  {})

    step = st.session_state["ob_step"]
    _html_step_bar(["Intake", "Forms", "DocuSign", "Post-Close"], step)

    # ── STEP 0: Intake ────────────────────────────────────────────────────────
    if step == 0:
        _html_section_header("Step 1 — Client Intake", "📥")

        col_src, col_info = st.columns([1, 1])
        with col_src:
            intake_src = st.radio(
                "Intake source",
                ["Registered client", "Upload intake form (.xlsx)"],
                key="ob_src",
            )

        ob_intake_data = {}

        with col_info:
            if intake_src == "Registered client":
                all_clients = _all_known_clients()
                if not all_clients:
                    st.warning("No registered clients. Register one first.")
                else:
                    ob_client = st.selectbox("Select client", all_clients, key="ob_client_sel")
                    entry = _registry_entry(ob_client)
                    if entry:
                        ob_intake_data = entry.get("intake", {})
                        st.success(f"✅ Loaded intake data for **{ob_client}**")
                    else:
                        st.warning("No registration data found for this client.")
            else:
                ob_upload = st.file_uploader("Upload intake form (.xlsx)", type=["xlsx"], key="ob_upload")
                if ob_upload:
                    try:
                        parsed = _read_intake_form(ob_upload)
                        if parsed:
                            # Merge all parsed parties into one intake dict with all fields
                            ob_intake_data = dict(parsed[0])
                            if len(parsed) >= 2:
                                ob_intake_data["Co-Account Holder Name"] = _full_name(parsed[1])
                                ob_intake_data["Co-Account Holder DOB"]  = parsed[1].get("Date of Birth","")
                            st.success(f"✅ Parsed {len(ob_intake_data)} fields")
                        else:
                            st.error("Could not parse intake form.")
                    except Exception as e:
                        st.error(f"Error reading file: {e}")

        if ob_intake_data:
            with st.expander("📋 Preview Extracted Data", expanded=False):
                display_rows = [(k, v) for k, v in ob_intake_data.items()
                                if not k.startswith("__") and v]
                df_preview = pd.DataFrame(display_rows, columns=["Field", "Value"])
                st.dataframe(df_preview, use_container_width=True, hide_index=True)

        st.markdown("")
        if st.button("▶  Analyze with AI →", type="primary", disabled=not ob_intake_data):
            with st.status("Analyzing intake data…", expanded=True) as sb:
                st.write("🤖 Claude is analyzing account types, funding paths, and form requirements…")
                intake_text = json.dumps(ob_intake_data, indent=2)
                raw_analysis = _onboarding_ai_analyze(intake_text)
                st.write("✅ Analysis complete")
                sb.update(label="Analysis complete!", state="complete")

            try:
                analysis = json.loads(raw_analysis)
            except Exception:
                analysis = {
                    "account_holders": [_full_name(ob_intake_data)],
                    "account_types": ["Individual"],
                    "funding_path": "Add Advisor to Existing Account",
                    "recommended_forms": ["IWSPersonalApp", "AddRemoveAdvisor"],
                    "notes": raw_analysis[:200],
                }

            st.session_state["ob_analysis"]       = analysis
            st.session_state["ob_intake"]          = ob_intake_data
            st.session_state["ob_holders"]         = analysis.get("account_holders", [_full_name(ob_intake_data)])
            st.session_state["ob_selected_forms"]  = analysis.get("recommended_forms", [])
            st.session_state["ob_step"]            = 1
            st.rerun()

    # ── STEP 1: Forms ─────────────────────────────────────────────────────────
    elif step == 1:
        analysis  = st.session_state["ob_analysis"] or {}
        intake    = st.session_state["ob_intake"]
        holders   = st.session_state["ob_holders"]
        sel_forms = st.session_state["ob_selected_forms"]

        _html_section_header("Step 2 — Form Selection & Pre-Fill", "📄")

        # AI summary callout
        acct_types   = analysis.get("account_types", [])
        funding_path = analysis.get("funding_path", "")
        ai_notes     = analysis.get("notes", "")
        if holders:
            _html_callout(
                f"<strong>Account Holders:</strong> {' &nbsp;|&nbsp; '.join(holders)}",
                "info",
            )
        if acct_types:
            _html_callout(
                f"<strong>Account Types Identified:</strong> {', '.join(acct_types)}",
                "info",
            )
        if funding_path:
            _html_callout(
                f"<strong>Funding Path:</strong> {funding_path}",
                "success",
            )
        if ai_notes:
            _html_callout(f"<strong>AI Notes:</strong> {ai_notes}", "info")

        st.markdown("")
        _html_section_header("Select Forms to Prepare", "☑")

        new_sel = []
        for fkey, fdata in FORM_CATALOG.items():
            recommended = fkey in sel_forms
            checked = st.checkbox(
                f"**{fdata['label']}**",
                value=recommended,
                key=f"ob_chk_{fkey}",
                help=fdata["desc"],
            )
            if checked:
                new_sel.append(fkey)
            # Show form description inline
            st.markdown(
                f'<div style="font-size:0.77rem;color:#334155;margin:-0.5rem 0 0.5rem 1.5rem;">'
                f'{fdata["desc"]}</div>',
                unsafe_allow_html=True,
            )

        st.session_state["ob_selected_forms"] = new_sel

        if new_sel:
            st.markdown("")
            _html_section_header("AI Pre-Fill Preview", "🤖")
            st.caption("Claude will map intake data to each form's required fields.")

            if _PDF_FILL_AVAILABLE:
                if st.button("📄 Fill & Download PDFs", type="primary"):
                    filled = {}
                    errors = []
                    with st.status("Filling PDFs with client data…", expanded=True) as sb:
                        # Build co_client dict from holders list if joint
                        co_client = None
                        if len(holders) > 1:
                            co_client = {"Full Name": holders[1]}
                        for fkey in new_sel:
                            fname = FORM_CATALOG[fkey]["label"]
                            st.write(f"📝 Filling: **{fname}**…")
                            try:
                                pdf_bytes = _pdf_filler.fill_form(
                                    fkey, intake, co_client=co_client
                                )
                                filled[fkey] = pdf_bytes
                                st.write(f"✅ Done: **{fname}**")
                            except Exception as e:
                                errors.append(f"{fname}: {e}")
                                st.write(f"⚠️ Error: **{fname}** — {e}")
                        sb.update(
                            label="PDFs ready for download!" if filled else "Completed with errors",
                            state="complete" if filled else "error",
                        )
                    st.session_state["ob_filled_pdfs"] = filled
                    st.rerun()
            else:
                if st.button("🔍 Generate Pre-Fill Preview", type="primary"):
                    prefills = {}
                    with st.status("Generating pre-fill data…", expanded=True) as sb:
                        for fkey in new_sel:
                            fname = FORM_CATALOG[fkey]["label"]
                            st.write(f"Filling: **{fname}**…")
                            raw_pf = _onboarding_ai_prefill(fkey, intake, holders)
                            try:
                                prefills[fkey] = json.loads(raw_pf)
                            except Exception:
                                prefills[fkey] = {"raw": raw_pf}
                        sb.update(label="Pre-fill complete!", state="complete")
                    st.session_state["ob_prefills"] = prefills
                    st.rerun()

            # Download buttons for filled PDFs
            if st.session_state["ob_filled_pdfs"]:
                st.markdown("")
                _html_section_header("Ready to Download", "⬇️")
                for fkey in new_sel:
                    pdf_bytes = st.session_state["ob_filled_pdfs"].get(fkey)
                    if pdf_bytes:
                        label    = FORM_CATALOG[fkey]["label"]
                        filename = f"FILLED_{FORM_CATALOG[fkey]['file']}"
                        col_name, col_btn = st.columns([3, 1])
                        with col_name:
                            st.markdown(
                                f'<div style="color:#E2E8F0;padding:0.5rem 0;">'
                                f'<span style="color:#10B981;">✓</span> &nbsp;{label}</div>',
                                unsafe_allow_html=True,
                            )
                        with col_btn:
                            st.download_button(
                                label="⬇️ Download",
                                data=pdf_bytes,
                                file_name=filename,
                                mime="application/pdf",
                                key=f"dl_{fkey}",
                            )

            # Optional: show prefill previews (AI mapping table)
            if st.session_state["ob_prefills"]:
                for fkey in new_sel:
                    pf = st.session_state["ob_prefills"].get(fkey, {})
                    if pf:
                        with st.expander(f"📝 {FORM_CATALOG[fkey]['label']} — Field Mapping"):
                            rows = [(k, v) for k, v in pf.items() if v and v != "—"]
                            if rows:
                                df_pf = pd.DataFrame(rows, columns=["Form Field", "Pre-Filled Value"])
                                st.dataframe(df_pf, use_container_width=True, hide_index=True)
                            else:
                                st.caption("No pre-fill data available for this form.")

        col_back, col_next = st.columns([1, 3])
        with col_back:
            if st.button("← Back"):
                st.session_state["ob_step"] = 0
                st.rerun()
        with col_next:
            if st.button("▶  Proceed to DocuSign →", type="primary", disabled=not new_sel):
                st.session_state["ob_step"] = 2
                st.rerun()

    # ── STEP 2: DocuSign ──────────────────────────────────────────────────────
    elif step == 2:
        intake    = st.session_state["ob_intake"]
        holders   = st.session_state["ob_holders"]
        sel_forms = st.session_state["ob_selected_forms"]

        _html_section_header("Step 3 — DocuSign Envelope", "✍️")

        # Recipient info
        email_primary = intake.get("Email", "")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            holder1_name  = holders[0] if holders else (intake.get("First Name","") + " " + intake.get("Last Name","")).strip()
            r1_name  = st.text_input("Account Holder 1 Name",  value=holder1_name,  key="ob_r1_name")
            r1_email = st.text_input("Account Holder 1 Email", value=email_primary, key="ob_r1_email")
        with col_r2:
            if len(holders) > 1:
                r2_name  = st.text_input("Account Holder 2 Name",  value=holders[1], key="ob_r2_name")
                r2_email = st.text_input("Account Holder 2 Email", value="",         key="ob_r2_email")
            else:
                r2_name  = ""
                r2_email = ""

        env_subject = st.text_input(
            "Envelope Subject",
            value=f"Your Account Documents — {holder1_name}",
            key="ob_env_subject",
        )
        env_message = st.text_area(
            "Personal Message (optional)",
            value=(
                f"Dear {holder1_name},\n\n"
                "Please review and sign the enclosed account documents at your earliest convenience. "
                "If you have any questions, don't hesitate to reach out.\n\n"
                "Thank you,"
            ),
            height=120,
            key="ob_env_message",
        )

        st.markdown("")
        _html_section_header("Forms to Include", "📎")
        for fkey in sel_forms:
            fdata = FORM_CATALOG.get(fkey, {})
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.5rem;padding:0.35rem 0;">'
                f'<span style="color:#10B981;font-size:0.85rem;">✓</span>'
                f'<span style="color:#94A3B8;font-size:0.85rem;">{fdata.get("label",fkey)}</span>'
                f'<span style="color:#334155;font-size:0.72rem;">({fdata.get("file","?")})</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        FORMS_DIR.mkdir(exist_ok=True)
        missing_pdfs = [
            FORM_CATALOG[fk]["file"] for fk in sel_forms
            if not (FORMS_DIR / FORM_CATALOG[fk]["file"]).exists()
        ]
        if missing_pdfs:
            _html_callout(
                f"<strong>PDF files not uploaded:</strong> {', '.join(missing_pdfs)}. "
                "Upload them to <code>forms/</code> to enable actual PDF pre-filling. "
                "DocuSign sending will proceed with placeholders.",
                "warning",
            )

        st.markdown("")
        col_preview, col_send = st.columns([1, 2])
        with col_preview:
            if st.button("📧 Preview Welcome Email"):
                st.session_state["ob_show_email_preview"] = True
        with col_send:
            if st.button("🚀 Send via DocuSign", type="primary"):
                with st.status("Sending DocuSign envelope…", expanded=True) as sb:
                    st.write(f"📧 Sending to: **{r1_email or r1_name}**")
                    if r2_email:
                        st.write(f"📧 CC: **{r2_email or r2_name}**")
                    for fkey in sel_forms:
                        st.write(f"📄 Queued: {FORM_CATALOG[fkey]['label']}")
                    import time; time.sleep(1)
                    sb.update(label="Envelope sent! (mock)", state="complete")
                    st.session_state["ob_envelope_sent"] = True
                    st.session_state["ob_step"] = 3
                st.rerun()

        if st.session_state.get("ob_show_email_preview"):
            with st.expander("📧 Welcome Email Preview", expanded=True):
                st.markdown(f"""
**To:** {r1_email or r1_name}
**Subject:** {env_subject}

---

{env_message}

---
*This message includes a DocuSign link for the following documents:*
{chr(10).join(f'• {FORM_CATALOG[fk]["label"]}' for fk in sel_forms)}
""")

        col_back2, _ = st.columns([1, 3])
        with col_back2:
            if st.button("← Back"):
                st.session_state["ob_step"] = 1
                st.rerun()

    # ── STEP 3: Post-Close Checklist ─────────────────────────────────────────
    elif step == 3:
        intake  = st.session_state["ob_intake"]
        holders = st.session_state["ob_holders"]
        sel_forms = st.session_state["ob_selected_forms"]

        _html_section_header("Step 4 — Post-Signature Checklist", "✅")

        holder1 = holders[0] if holders else "Client"

        if st.session_state.get("ob_envelope_sent"):
            _html_callout(
                f"<strong>DocuSign envelope sent</strong> to {holder1}. "
                "Track signature status below and complete post-close steps when signed.",
                "success",
            )

        # Signature status tracker
        _html_section_header("Signature Status", "📊")
        sig_col1, sig_col2 = st.columns(2)
        with sig_col1:
            for fkey in sel_forms:
                status_key = f"ob_sig_{fkey}"
                st.session_state.setdefault(status_key, "Pending")
                current = st.session_state[status_key]
                color   = "#10B981" if current == "Signed" else "#F59E0B" if current == "Pending" else "#EF4444"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:0.4rem 0;border-bottom:1px solid rgba(0,212,255,0.08);">'
                    f'<span style="color:#94A3B8;font-size:0.83rem;">{FORM_CATALOG[fkey]["label"]}</span>'
                    f'<span style="color:{color};font-size:0.75rem;font-weight:700;">{current}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        with sig_col2:
            for fkey in sel_forms:
                status_key = f"ob_sig_{fkey}"
                new_status = st.selectbox(
                    FORM_CATALOG[fkey]["label"],
                    ["Pending", "Signed", "Declined"],
                    index=["Pending","Signed","Declined"].index(st.session_state.get(status_key,"Pending")),
                    key=f"ob_sigsel_{fkey}",
                    label_visibility="collapsed",
                )
                st.session_state[status_key] = new_status

        # Post-close action checklist
        st.markdown("")
        _html_section_header("Post-Signature Actions", "📋")

        post_tasks = [
            ("fidelity",     "Add accounts to Fidelity"),
            ("black_diamond", "Add client to Black Diamond (reporting)"),
            ("ima_billing",   "Send IMA to Billing & Compliance"),
            ("welcome_call",  "Schedule welcome call with client"),
            ("crm_update",    "Update CRM with account numbers and onboarding date"),
        ]

        all_done = True
        for task_key, task_label in post_tasks:
            session_key = f"ob_post_{task_key}"
            st.session_state.setdefault(session_key, False)
            checked = st.checkbox(task_label, value=st.session_state[session_key], key=f"ob_chk_post_{task_key}")
            st.session_state[session_key] = checked
            if not checked:
                all_done = False

        st.markdown("")
        if all_done:
            _html_callout(
                f"<strong>🎉 Onboarding Complete!</strong> All post-close steps checked off for {holder1}.",
                "success",
            )
        else:
            remaining = sum(1 for k, _ in post_tasks if not st.session_state.get(f"ob_post_{k}", False))
            _html_callout(
                f"<strong>{remaining} step{'s' if remaining != 1 else ''} remaining</strong> in post-close checklist.",
                "warning",
            )

        st.markdown("")
        _html_section_header("Onboarding Summary", "📊")
        _html_stat_row([
            ("Account Holders", str(len(holders))),
            ("Forms Prepared",  str(len(sel_forms))),
            ("DocuSign Status", "Sent" if st.session_state.get("ob_envelope_sent") else "Not Sent"),
            ("Post-Close",      f"{sum(1 for k,_ in post_tasks if st.session_state.get(f'ob_post_{k}'))}/{len(post_tasks)}"),
        ])

        st.markdown("")
        if st.button("⟳  Start New Onboarding", type="primary"):
            for key in list(st.session_state.keys()):
                if key.startswith("ob_"):
                    del st.session_state[key]
            st.rerun()

    _html_footer()
