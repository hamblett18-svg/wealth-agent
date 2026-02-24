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

# ─────────────────────────────────────────────────────────────────────────────
# CSS — Navy / Gold enterprise theme
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Variables ── */
:root {
  --navy:   #0D1B3C;
  --navy2:  #1A2F5A;
  --navy3:  #2D4A7A;
  --gold:   #C8A951;
  --gold2:  #E8C878;
  --white:  #FFFFFF;
  --bg:     #EEF1F7;
  --card:   #FFFFFF;
  --border: #DDE3EE;
  --txt:    #1A1F36;
  --txt2:   #4A5568;
  --txt3:   #718096;
  --green:  #1E6B3C;
  --red:    #9B1B1B;
  --amber:  #B45309;
}

/* ── Base ── */
html, body, [class*="css"] {
  font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  color: var(--txt);
}
.stApp { background: var(--bg); }
.main .block-container {
  padding-top: 1.25rem;
  padding-bottom: 5rem;
  max-width: 1440px;
}
footer { visibility: hidden; }

/* ── Sidebar ── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {
  background: linear-gradient(175deg, #080F20 0%, #0D1B3C 55%, #152545 100%) !important;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] span { color: #7A8DAA !important; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] label p,
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stRadio label p,
[data-testid="stSidebar"] [data-testid="stRadio"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] label p,
[data-testid="stSidebar"] [data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p {
  color: #FFFFFF !important;
  font-weight: 500 !important;
}
[data-testid="stSidebar"] .stCaption p { color: #3A4A62 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(200,169,81,0.15) !important; }
[data-testid="stSidebar"] .stButton > button {
  background: rgba(200,169,81,0.08) !important;
  border: 1px solid rgba(200,169,81,0.3) !important;
  color: #C8A951 !important;
  border-radius: 5px !important;
  font-size: 0.82rem !important;
  width: 100%;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(200,169,81,0.2) !important;
  border-color: rgba(200,169,81,0.7) !important;
}

/* ── Typography ── */
h1 {
  color: var(--navy) !important;
  font-size: 1.55rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.02em;
}
h2 {
  color: var(--navy2) !important;
  font-size: 1.1rem !important;
  font-weight: 600 !important;
  margin-top: 1.5rem !important;
}
h3 {
  color: var(--navy2) !important;
  font-size: 0.9rem !important;
  font-weight: 600 !important;
}

/* ── Buttons ── */
.stButton > button[kind="primary"] {
  background: var(--navy) !important;
  color: var(--gold) !important;
  border: 1px solid rgba(200,169,81,0.5) !important;
  border-radius: 6px !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em !important;
  padding: 0.45rem 1.25rem !important;
  transition: all 0.18s ease !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--navy2) !important;
  box-shadow: 0 4px 14px rgba(13,27,60,0.3) !important;
  transform: translateY(-1px) !important;
}
.stButton > button:not([kind="primary"]) {
  background: white !important;
  color: var(--navy2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 6px !important;
  font-weight: 500 !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"],
[data-testid="stMetric"] {
  background: white !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  padding: 1rem 1.25rem !important;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
  border-left: 4px solid var(--gold) !important;
}
[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] {
  color: var(--txt3) !important;
  font-size: 0.66rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
}
[data-testid="stMetricValue"] {
  color: var(--navy) !important;
  font-weight: 800 !important;
}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  overflow: hidden !important;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] { border-radius: 7px !important; }

/* ── Chat ── */
[data-testid="stChatMessage"] {
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
  margin-bottom: 0.6rem !important;
}

/* ── Inputs ── */
.stSelectbox [data-baseweb="select"] > div,
.stTextInput input {
  border-radius: 6px !important;
  border-color: var(--border) !important;
  background: white !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
  background: white !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  color: var(--navy2) !important;
  font-size: 0.87rem !important;
}

/* ── Divider / HR ── */
hr { border-color: var(--border) !important; margin: 1.25rem 0 !important; }

/* ── Status widget ── */
[data-testid="stStatusWidget"] {
  border-radius: 8px !important;
  border: 1px solid var(--border) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
  border: 2px dashed var(--border) !important;
  border-radius: 8px !important;
  background: white !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HTML UI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _html_page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    icon_html = f'<span style="font-size:1.6rem;margin-right:0.4rem;">{icon}</span>' if icon else ""
    sub_html  = f'<p style="color:#718096;font-size:0.88rem;margin:0.25rem 0 0;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
<div style="margin-bottom:1.5rem;">
  <div style="display:flex;align-items:center;">
    {icon_html}
    <h1 style="margin:0;padding:0;">{title}</h1>
  </div>
  <div style="height:2px;background:linear-gradient(90deg,#C8A951 0%,rgba(200,169,81,0.15) 100%);
       margin:0.4rem 0 0.3rem;border:none;"></div>
  {sub_html}
</div>
""", unsafe_allow_html=True)


def _html_section_header(title: str, icon: str = "") -> None:
    icon_html = f"{icon}&nbsp;" if icon else ""
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.4rem;margin:1.6rem 0 0.6rem;
     padding-bottom:0.45rem;border-bottom:2px solid #DDE3EE;">
  <span style="font-size:1.05rem;">{icon_html}</span>
  <span style="color:#1A2F5A;font-size:0.78rem;font-weight:700;
        text-transform:uppercase;letter-spacing:0.08em;">{title}</span>
</div>
""", unsafe_allow_html=True)


def _html_client_badge(name: str, has_excel: bool, has_registry: bool) -> None:
    tags = []
    if has_registry:
        tags.append(
            '<span style="background:rgba(200,169,81,0.1);color:#7A5F1A;border:1px solid '
            'rgba(200,169,81,0.35);border-radius:4px;padding:1px 8px;font-size:0.68rem;'
            'font-weight:700;">📋 Profile</span>'
        )
    if has_excel:
        tags.append(
            '<span style="background:rgba(13,27,60,0.06);color:#1A2F5A;border:1px solid '
            'rgba(13,27,60,0.15);border-radius:4px;padding:1px 8px;font-size:0.68rem;'
            'font-weight:700;">📊 Account Data</span>'
        )
    else:
        tags.append(
            '<span style="background:rgba(180,83,9,0.08);color:#92400E;border:1px solid '
            'rgba(180,83,9,0.25);border-radius:4px;padding:1px 8px;font-size:0.68rem;'
            'font-weight:700;">⚠ No Account Data</span>'
        )
    initials = "".join(p[0].upper() for p in name.split()[:2]) if name else "?"
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.85rem;padding:0.75rem 1rem;
     background:white;border:1px solid #DDE3EE;border-radius:9px;margin-bottom:1rem;
     box-shadow:0 1px 4px rgba(0,0,0,0.05);">
  <div style="width:42px;height:42px;background:#0D1B3C;border-radius:50%;
       display:flex;align-items:center;justify-content:center;
       color:#C8A951;font-size:0.95rem;font-weight:800;flex-shrink:0;">{initials}</div>
  <div>
    <div style="font-weight:700;color:#0D1B3C;font-size:1.02rem;line-height:1.2;">{name}</div>
    <div style="display:flex;gap:0.3rem;margin-top:4px;">{" ".join(tags)}</div>
  </div>
</div>
""", unsafe_allow_html=True)


def _html_callout(text: str, level: str = "info") -> None:
    """Advisor-grade callout box. level: 'info' | 'warning' | 'alert'"""
    cfg = {
        "info":    ("#EBF8FF", "#2B6CB0", "#BEE3F8", "ℹ"),
        "warning": ("#FFFBEB", "#92400E", "#FDE68A", "⚠"),
        "alert":   ("#FFF5F5", "#9B1B1B", "#FEB2B2", "🚨"),
        "success": ("#F0FFF4", "#1E6B3C", "#9AE6B4", "✓"),
    }
    bg, tc, border, icon = cfg.get(level, cfg["info"])
    st.markdown(f"""
<div style="background:{bg};border-left:4px solid {border};border-radius:0 7px 7px 0;
     padding:0.65rem 1rem;margin:0.4rem 0;font-size:0.88rem;color:{tc};">
  {icon}&nbsp; {text}
</div>
""", unsafe_allow_html=True)


def _html_stat_row(stats: list) -> None:
    """stats = [(label, value), ...]  — renders custom HTML stat cards in equal columns."""
    n = len(stats)
    w = f"calc({100/n}% - {(n-1)*8/n:.1f}px)"
    cards = ""
    for label, value in stats:
        cards += f"""
<div style="flex:1;background:white;border:1px solid #DDE3EE;border-radius:8px;
     padding:0.9rem 1.1rem;box-shadow:0 1px 4px rgba(0,0,0,0.05);
     border-left:4px solid #C8A951;">
  <div style="color:#718096;font-size:0.65rem;font-weight:700;text-transform:uppercase;
       letter-spacing:0.08em;">{label}</div>
  <div style="color:#0D1B3C;font-size:1.3rem;font-weight:800;margin-top:2px;
       font-variant-numeric:tabular-nums;">{value}</div>
</div>"""
    st.markdown(
        f'<div style="display:flex;gap:0.75rem;margin:0.75rem 0;">{cards}</div>',
        unsafe_allow_html=True,
    )


def _html_footer() -> None:
    year = datetime.now().year
    st.markdown(f"""
<div style="margin-top:3rem;padding:0.9rem 1.5rem;background:#0D1B3C;
     border-radius:8px;display:flex;justify-content:space-between;align-items:center;">
  <span style="color:#C8A951;font-size:0.72rem;font-weight:700;letter-spacing:0.1em;">
    ⬡ {BRAND.upper()}
  </span>
  <span style="color:rgba(255,255,255,0.3);font-size:0.68rem;letter-spacing:0.06em;">
    {PRODUCT} &nbsp;·&nbsp; © {year} &nbsp;·&nbsp; Powered by Claude
  </span>
  <span style="color:rgba(255,255,255,0.25);font-size:0.68rem;">
    {datetime.now().strftime('%B %d, %Y')}
  </span>
</div>
""", unsafe_allow_html=True)


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
    spouse = intake.get("Spouse Name", "")
    if spouse:
        bene_parts.append(f"Spouse: {spouse}, DOB {intake.get('Spouse DOB','')}")
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
    """Unified list: all registered clients PLUS any Excel-only clients, deduped."""
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
# Elite AI Advisor system prompt
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

For "How should I approach this meeting?" → Provide a structured agenda with time estimates
For "What are the red flags?" → Rank by severity with specific remediation steps
For "What are the opportunities?" → Name the action and estimate the dollar impact
For "Tax implications?" → Compute the actual numbers, not generic CPA advice
For "What should I discuss?" → Prioritized talking points in the exact order to raise them
For "Anything I'm missing?" → Comprehensive proactive sweep of the full picture

If account data is missing, say so clearly in one sentence, then give the best analysis
possible from the profile data available. Never invent data.

━━━ CLIENT DATA ━━━
<client_context>
{context}
</client_context>"""


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    # Brand header
    st.markdown(f"""
<div style="padding:0.5rem 0 1.1rem;text-align:center;
     border-bottom:1px solid rgba(200,169,81,0.15);margin-bottom:1rem;">
  <div style="color:#C8A951;font-size:1.05rem;font-weight:800;letter-spacing:0.04em;
       font-family:'Inter',sans-serif;">⬡ {BRAND}</div>
  <div style="color:rgba(255,255,255,0.25);font-size:0.6rem;letter-spacing:0.12em;
       margin-top:3px;text-transform:uppercase;">{PRODUCT}</div>
</div>
""", unsafe_allow_html=True)

    # API status
    if HAS_API_KEY:
        st.markdown(
            '<div style="background:rgba(30,107,60,0.2);border:1px solid rgba(30,107,60,0.4);'
            'border-radius:5px;padding:5px 10px;font-size:0.75rem;color:#6BCF8F;'
            'text-align:center;margin-bottom:0.5rem;">🟢 Live AI Mode</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:rgba(180,83,9,0.15);border:1px solid rgba(180,83,9,0.35);'
            'border-radius:5px;padding:5px 10px;font-size:0.75rem;color:#F6AD55;'
            'text-align:center;margin-bottom:0.5rem;">🟡 Mock Mode — no API key</div>',
            unsafe_allow_html=True,
        )
    st.divider()

    # Navigation
    st.markdown(
        '<div style="color:rgba(255,255,255,0.3);font-size:0.62rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.12em;margin-bottom:0.4rem;">Navigation</div>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "nav",
        ["Register Client", "Meeting Prep", "AI Advisor"],
        label_visibility="collapsed",
    )
    st.divider()

    # Generate sample data
    if st.button("⚙  Generate Sample Data", use_container_width=True):
        with st.spinner("Creating sample files…"):
            create_dummy_data()
        st.success("Sample data created.")
        st.rerun()

    # Status indicators
    st.divider()
    if _data_ready():
        st.caption(f"✅ Data: `{DATA_DIR}/`")
    else:
        st.caption("⚠ No data — click Generate above")

    all_clients = _all_known_clients()
    if all_clients:
        st.markdown(
            '<div style="color:rgba(255,255,255,0.3);font-size:0.62rem;font-weight:700;'
            'text-transform:uppercase;letter-spacing:0.1em;margin:0.5rem 0 0.3rem;">'
            'Known Clients</div>',
            unsafe_allow_html=True,
        )
        for cn in all_clients:
            has_xl  = _client_has_excel(cn)
            dot_col = "#C8A951" if has_xl else "#4A5A78"
            st.markdown(
                f'<div style="font-size:0.78rem;color:#7A8DAA;padding:1px 0;">'
                f'<span style="color:{dot_col};">●</span> {cn}</div>',
                unsafe_allow_html=True,
            )


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
        primary  = dict(parsed_clients[0])
        spouse   = parsed_clients[1]
        primary["Spouse Name"] = _full_name(spouse)
        primary["Spouse DOB"]  = spouse.get("Date of Birth", "")
        children = parsed_clients[2:]
        for idx, child in enumerate(children, start=1):
            primary[f"Child {idx} Name"] = _full_name(child)
            primary[f"Child {idx} DOB"]  = child.get("Date of Birth", "")
        selected_intake = primary
        summary = f"👨‍👩‍👧 **Primary:** {_full_name(primary)}   |   **Spouse:** {primary['Spouse Name']}"
        if children:
            summary += f"   |   **Children:** {', '.join(_full_name(c) for c in children)}"
        st.info(summary)
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

        # Stat row
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
            if intake.get("Spouse Name"):
                rows.append(("Spouse",     intake["Spouse Name"]))
            if intake.get("Spouse DOB"):
                rows.append(("Spouse DOB", intake["Spouse DOB"]))
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

    # ── Unified client selector (all registered + excel clients) ──────────
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

    # Upload account data for profile-only clients
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
                    dest = _save_account_data(upload_target, upload_file.read())
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

    # ── Display results ────────────────────────────────────────────────────
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
            # ── Full account analysis ──────────────────────────────────────
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
            # ── Profile-only brief (no Excel) ─────────────────────────────
            _html_callout(
                "This client has a registration profile but no account data on file. "
                "Upload an Excel workbook in the section above to unlock the full briefing.",
                "warning",
            )
            st.markdown("")

            # Financial profile stats
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

                if intake.get("Spouse Name"):
                    st.markdown(f"**Spouse:** {intake['Spouse Name']}")
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

    # ── Client selector ────────────────────────────────────────────────────
    saved_aac   = st.session_state.get("aac_client", all_clients[0])
    default_i   = all_clients.index(saved_aac) if saved_aac in all_clients else 0
    sel_client  = st.selectbox("Select client", all_clients, index=default_i)

    if sel_client != st.session_state.get("aac_client"):
        st.session_state["aac_client"]  = sel_client
        st.session_state["aac_history"] = []
        st.rerun()

    st.session_state.setdefault("aac_history", [])
    history: list = st.session_state["aac_history"]

    # Client badge
    reg   = _registry_entry(sel_client)
    xl_ok = _client_has_excel(sel_client)
    _html_client_badge(sel_client, has_excel=xl_ok, has_registry=bool(reg))

    if not reg and not xl_ok:
        _html_callout("No data found for this client. Register them first.", "alert")
        _html_footer()
        st.stop()

    # Suggested questions
    st.markdown(
        '<div style="color:#718096;font-size:0.78rem;margin-bottom:0.75rem;">'
        '💡 <em>Try asking:</em> &nbsp;'
        '"How should I approach this meeting?" &nbsp;·&nbsp; '
        '"What are the red flags?" &nbsp;·&nbsp; '
        '"Walk me through the tax picture" &nbsp;·&nbsp; '
        '"What opportunities am I missing?"'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Chat history ───────────────────────────────────────────────────────
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Input ──────────────────────────────────────────────────────────────
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
                # Pass full history (including just-appended question) — trim to last 30 turns
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
                # ── Mock mode ─────────────────────────────────────────────
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

                if any(w in q_lower for w in ("approach", "meeting", "agenda", "prepare", "talk")):
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
                elif any(w in q_lower for w in ("aum", "total", "value", "balance", "portfolio")):
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
                            f"• Estimated taxes paid: **{_fmt_money(taxes)}**\n"
                            f"• ST Gains: {_fmt_money(tax_map.get('Realized ST Gains',0))} | "
                            f"LT Gains: {_fmt_money(tax_map.get('Realized LT Gains',0))}\n\n"
                            f"**PROACTIVE INSIGHTS**\n"
                            f"• {'Consider TLH opportunities' if net_gl < 0 else 'Coordinate with CPA on gain offset'}\n\n"
                            f"*(Mock mode)*"
                        )
                    else:
                        full_response = "No tax data on file. Upload account workbook for tax analysis."
                elif any(w in q_lower for w in ("allocation","drift","rebalance","asset","weight")):
                    if alloc_rows:
                        lines = [_mock_preamble(), "**DIRECT ANSWER — Allocation**\n"]
                        for r in alloc_rows:
                            drift = r.get("Drift","")
                            try:
                                dval = float(str(drift).replace("%","").replace("+",""))
                                flag = " ⚠" if abs(dval) >= 2.0 else ""
                            except ValueError:
                                flag = ""
                            lines.append(f"• {r.get('Asset Class','')}: {r.get('Current %','')}% "
                                         f"(target {r.get('Target %','')}%, drift {drift}){flag}")
                        full_response = "\n".join(lines) + "\n\n*(Mock mode)*"
                    else:
                        full_response = "No allocation data on file. Upload account workbook."
                elif any(w in q_lower for w in ("risk","goal","objective","horizon","tolerance")):
                    parts = [_mock_preamble(), "**DIRECT ANSWER — Investment Profile**\n"]
                    for f in ("Risk Tolerance","Investment Goal","Time Horizon (yrs)"):
                        if intake.get(f):
                            parts.append(f"• {f}: **{intake[f]}**")
                    full_response = "\n".join(parts) + "\n\n*(Mock mode)*"
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

    # ── Clear button + session info ────────────────────────────────────────
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
