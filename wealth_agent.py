#!/usr/bin/env python3
"""
Wealth Management AI Agent — powered by Claude

Commands:
    setup                          Create sample Excel data files
    register [--intake PATH]       Read intake form, create Salesforce record
    meeting-prep "Client Name"     Generate advisor one-pager for a client

Quick start:
    pip install anthropic pandas openpyxl
    export ANTHROPIC_API_KEY=sk-ant-...
    python wealth_agent.py setup
    python wealth_agent.py register
    python wealth_agent.py meeting-prep "Robert Thornton"

Mock mode (no API key required):
    python wealth_agent.py --mock register
    python wealth_agent.py --mock meeting-prep "Robert Thornton"
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

import anthropic
from anthropic import beta_tool
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR    = Path("data")
CLIENTS_DIR = DATA_DIR / "clients"
MODEL       = "claude-sonnet-4-5-20250929"

# ─────────────────────────────────────────────────────────────────────────────
# Mock Salesforce Client
# Swap this class for a real simple_salesforce / requests call when you have
# live credentials.  The interface (create_contact / print_records) stays the same.
# ─────────────────────────────────────────────────────────────────────────────

class MockSalesforce:
    """In-memory simulation of the Salesforce Contact API."""

    _records: dict = {}
    _seq: int = 1000

    @classmethod
    def create_contact(cls, fields: dict) -> dict:
        sf_id  = f"003{cls._seq:013d}"
        cls._seq += 1
        record = {
            "Id":          sf_id,
            "RecordType":  "WealthManagementClient",
            "CreatedDate": datetime.utcnow().isoformat() + "Z",
            **fields,
        }
        cls._records[sf_id] = record
        return {"success": True, "id": sf_id, "errors": []}

    @classmethod
    def print_records(cls) -> None:
        if not cls._records:
            return
        print("\n── Mock Salesforce — stored records ─────────────────────────────")
        for rec in cls._records.values():
            print(json.dumps(rec, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Dummy Data Generator
# ─────────────────────────────────────────────────────────────────────────────

def create_dummy_data() -> None:
    """Write sample Excel files that the agent will read during the demo."""
    DATA_DIR.mkdir(exist_ok=True)
    CLIENTS_DIR.mkdir(exist_ok=True)

    # ── Intake form (new-client registration) ────────────────────────────────
    intake_rows = [
        ("First Name",           "Robert"),
        ("Last Name",            "Thornton"),
        ("Date of Birth",        "1968-04-15"),
        ("SSN Last 4",           "4721"),
        ("Address",              "1847 Lakeshire Dr"),
        ("City",                 "Naperville"),
        ("State",                "IL"),
        ("ZIP",                  "60540"),
        ("Phone",                "(630) 555-0192"),
        ("Email",                "r.thornton@email.com"),
        ("Employer",             "Thornton Manufacturing Inc."),
        ("Annual Income",        "285000"),
        ("Occupation",           "CEO"),
        ("Risk Tolerance",       "Moderate-Aggressive"),
        ("Investment Goal",      "Retirement & Wealth Preservation"),
        ("Time Horizon (yrs)",   "15"),
        ("Spouse Name",          "Linda Thornton"),
        ("Spouse DOB",           "1970-09-22"),
        ("Beneficiary 1 Name",   "Robert Thornton Jr."),
        ("Beneficiary 1 Rel",    "Son"),
        ("Beneficiary 1 Pct",    "50"),
        ("Beneficiary 2 Name",   "Sarah Thornton"),
        ("Beneficiary 2 Rel",    "Daughter"),
        ("Beneficiary 2 Pct",    "50"),
        ("Est. Net Worth",       "3200000"),
        ("Liquid Assets",        "850000"),
        ("Existing Advisor",     "None"),
        ("Referral Source",      "Business colleague"),
    ]
    pd.DataFrame(intake_rows, columns=["Field", "Value"]).to_excel(
        DATA_DIR / "client_intake.xlsx", sheet_name="Intake Form", index=False
    )

    # ── Existing client data file (meeting prep) ─────────────────────────────
    with pd.ExcelWriter(CLIENTS_DIR / "robert_thornton.xlsx", engine="openpyxl") as w:

        # Account Summary
        pd.DataFrame({
            "Account":      ["IRA Rollover", "Brokerage Taxable", "Roth IRA",  "Joint Taxable"],
            "Account #":    ["IRA-7741",     "BRK-2293",          "RTH-0847",  "JNT-5512"],
            "Market Value": [1_245_000,       875_000,             320_000,     560_000],
            "As of Date":   ["2024-12-31"] * 4,
        }).to_excel(w, sheet_name="Account Summary", index=False)

        # Distributions & Contributions YTD
        pd.DataFrame({
            "Date":        ["2024-01-15",   "2024-03-01",              "2024-06-15",   "2024-09-01",  "2024-12-01"],
            "Type":        ["Contribution", "Distribution",            "Contribution", "Distribution","Contribution"],
            "Account":     ["IRA-7741",     "BRK-2293",                "RTH-0847",     "IRA-7741",    "JNT-5512"],
            "Amount ($)":  [7_000,          -25_000,                   7_000,          -18_500,       15_000],
            "Description": [
                "Annual IRA Contribution",
                "Quarterly Income Distribution",
                "Roth IRA Contribution",
                "RMD Distribution",
                "Year-End Contribution",
            ],
        }).to_excel(w, sheet_name="Distributions & Contributions", index=False)

        # Tax & Realized G/L
        pd.DataFrame({
            "Category": [
                "Est. Tax Payment Q1", "Est. Tax Payment Q2",
                "Est. Tax Payment Q3", "Est. Tax Payment Q4",
                "Realized ST Gains",   "Realized LT Gains",
                "Realized ST Losses",  "Realized LT Losses",
                "Qualified Dividends", "Non-Qual Dividends",  "Interest Income",
            ],
            "Amount ($)": [
                28_500, 28_500, 28_500, 28_500,
                42_300, 87_500,
                -12_400, -8_750,
                18_600, 3_200, 4_750,
            ],
            "Notes": [
                "Federal + State", "Federal + State",
                "Federal + State", "Federal + State (est.)",
                "Tech sector rebalance", "Long-hold exits",
                "Tax-loss harvesting",   "Tax-loss harvesting",
                "S&P 500 ETF",           "REIT holdings", "Bond ladder",
            ],
        }).to_excel(w, sheet_name="Tax & Realized GL", index=False)

        # Beneficiaries
        pd.DataFrame({
            "Name":         ["Robert Thornton Jr.", "Sarah Thornton",      "Linda Thornton"],
            "Relationship": ["Son",                  "Daughter",            "Spouse"],
            "Pct":          [50,                      50,                    100],
            "Account(s)":   ["IRA-7741/RTH-0847",     "IRA-7741/RTH-0847",  "JNT-5512"],
            "DOB":          ["1998-07-12",             "2001-03-28",          "1970-09-22"],
        }).to_excel(w, sheet_name="Beneficiaries", index=False)

        # Allocation
        pd.DataFrame({
            "Asset Class": [
                "US Large Cap Equity", "US Small/Mid Cap", "International Equity",
                "Emerging Markets",    "US Core Bonds",    "High Yield Bonds",
                "REITs",               "Alternatives",     "Cash",
            ],
            "Target %":      [30,    8,   12,   5,    25,    5,    5,    8,    2],
            "Current %":     [32.4,  7.1, 11.8, 4.9,  24.2,  5.3,  5.8,  6.7,  1.8],
            "Market Value":  [972_000, 213_000, 354_000, 147_000, 726_000, 159_000, 174_000, 201_000, 54_000],
            "Drift":         ["+2.4%","-0.9%","-0.2%","-0.1%","-0.8%","+0.3%","+0.8%","-1.3%","-0.2%"],
        }).to_excel(w, sheet_name="Allocation", index=False)

    print("Sample files created:")
    print(f"  {DATA_DIR}/client_intake.xlsx      — new client intake form")
    print(f"  {CLIENTS_DIR}/robert_thornton.xlsx — existing client data (5 sheets)")


# ─────────────────────────────────────────────────────────────────────────────
# Tool Definitions
# @beta_tool generates the JSON schema from type hints + the Args: docstring.
# Claude decides when and how to call each tool; the SDK handles the loop.
# In mock mode these same functions are called directly, bypassing the API.
# ─────────────────────────────────────────────────────────────────────────────

@beta_tool
def list_excel_sheets(file_path: str) -> str:
    """List all sheet names in an Excel workbook.

    Args:
        file_path: Path to the .xlsx file (relative or absolute).
    """
    try:
        return json.dumps({"sheets": pd.ExcelFile(file_path).sheet_names})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@beta_tool
def read_excel_sheet(file_path: str, sheet_name: str) -> str:
    """Read all rows from a named sheet in an Excel file and return them as JSON.

    Args:
        file_path: Path to the .xlsx file.
        sheet_name: Exact name of the sheet to read.
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str)
        return json.dumps(df.fillna("").to_dict(orient="records"))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@beta_tool
def find_client_file(client_name: str) -> str:
    """Search for a client's Excel data file by their full name.

    Args:
        client_name: Client full name, e.g. 'Robert Thornton'.
    """
    slug      = re.sub(r"[^\w]+", "_", client_name.lower()).strip("_") + ".xlsx"
    all_files = list(CLIENTS_DIR.glob("*.xlsx"))

    # Exact slug match
    for f in all_files:
        if f.name == slug:
            return json.dumps({"found": True, "path": str(f),
                                "sheets": pd.ExcelFile(str(f)).sheet_names})

    # Partial: all name parts (apostrophes stripped) somewhere in the stem
    parts = re.sub(r"[^a-z0-9 ]", "", client_name.lower()).split()
    for f in all_files:
        if all(p in f.stem for p in parts):
            return json.dumps({"found": True, "path": str(f),
                                "sheets": pd.ExcelFile(str(f)).sheet_names})

    available = [f.stem.replace("_", " ").title() for f in all_files]
    return json.dumps({
        "found":     False,
        "tip":       "Run: python wealth_agent.py setup",
        "available": available,
    })


@beta_tool
def create_salesforce_contact(
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    date_of_birth: str,
    mailing_street: str,
    mailing_city: str,
    mailing_state: str,
    mailing_zip: str,
    annual_income: str,
    employer: str,
    occupation: str,
    risk_tolerance: str,
    investment_goal: str,
    time_horizon_years: str,
    net_worth: str,
    liquid_assets: str,
    lead_source: str = "",
    notes: str = "",
) -> str:
    """Create a new wealth management client record in Salesforce CRM.

    Args:
        first_name: Client first name.
        last_name: Client last name.
        email: Email address.
        phone: Phone number.
        date_of_birth: Date of birth in YYYY-MM-DD format.
        mailing_street: Street address.
        mailing_city: City.
        mailing_state: Two-letter state abbreviation (e.g. IL).
        mailing_zip: ZIP or postal code.
        annual_income: Gross annual income as a numeric string — digits only, no $ or commas.
        employer: Employer or company name.
        occupation: Job title or occupation.
        risk_tolerance: Risk tolerance classification, e.g. Moderate-Aggressive.
        investment_goal: Primary investment objective.
        time_horizon_years: Investment time horizon in years (numeric string).
        net_worth: Estimated total net worth — digits only, no $ or commas.
        liquid_assets: Estimated liquid assets — digits only, no $ or commas.
        lead_source: Referral or lead source (optional).
        notes: Additional advisor notes such as beneficiary details (optional).
    """
    result = MockSalesforce.create_contact({
        "FirstName":          first_name,
        "LastName":           last_name,
        "Email":              email,
        "Phone":              phone,
        "Birthdate":          date_of_birth,
        "MailingStreet":      mailing_street,
        "MailingCity":        mailing_city,
        "MailingState":       mailing_state,
        "MailingPostalCode":  mailing_zip,
        "Annual_Income__c":   annual_income,
        "AccountName":        employer,
        "Title":              occupation,
        "Risk_Tolerance__c":  risk_tolerance,
        "Investment_Goal__c": investment_goal,
        "Time_Horizon__c":    time_horizon_years,
        "Net_Worth__c":       net_worth,
        "Liquid_Assets__c":   liquid_assets,
        "LeadSource":         lead_source,
        "Description":        notes,
    })
    return json.dumps(result)


# ─────────────────────────────────────────────────────────────────────────────
# System Prompts
# ─────────────────────────────────────────────────────────────────────────────

REGISTER_SYSTEM = """\
You are a wealth management onboarding assistant.

Your job:
1. Read the client intake Excel form using list_excel_sheets then read_excel_sheet.
2. Map every field to the correct Salesforce parameter accurately.
   - Dates must be YYYY-MM-DD format.
   - Numeric fields (income, net worth, liquid assets) must be digits only — no $ or commas.
   - Put beneficiary details in the notes field.
3. Call create_salesforce_contact exactly once with all extracted data.
4. After the record is created, print a clean confirmation summary for the advisor."""

MEETING_PREP_SYSTEM = """\
You are a senior wealth management associate preparing a meeting brief for an advisor.

Steps:
1. Call find_client_file to locate the client's Excel workbook.
2. Call read_excel_sheet for EVERY sheet in that file.
3. Synthesize everything into a professional one-pager.

The one-pager must have these labeled sections in order:

  CLIENT SNAPSHOT
  ACCOUNT SUMMARY
  DISTRIBUTIONS & CONTRIBUTIONS (YTD)
  TAX SUMMARY (YTD)
  BENEFICIARIES
  CURRENT ALLOCATION vs. TARGET
  ADVISOR TALKING POINTS

Use clean plain-text formatting with aligned columns where helpful.
Flag anything notable: allocation drift >2%, upcoming RMDs, concentrated positions,
tax-loss harvesting opportunities, or anything else the advisor should raise.
Keep it tight — one printed page."""


# ─────────────────────────────────────────────────────────────────────────────
# Agent Runner (real mode — requires ANTHROPIC_API_KEY)
# ─────────────────────────────────────────────────────────────────────────────

def _run_agent(system: str, user_msg: str, tools: list, header: str) -> None:
    """Execute the tool-runner loop, print progress, and display final output."""
    client = anthropic.Anthropic()

    print(f"\n{'━' * 60}")
    print(f"  {header}")
    print(f"{'━' * 60}\n")

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=8192,
        system=system,
        tools=tools,
        messages=[{"role": "user", "content": user_msg}],
    )

    # The runner yields a BetaMessage on each iteration:
    #   - Early messages contain tool_use blocks (Claude calling your tools)
    #   - The final message contains the text response
    for msg in runner:
        for block in msg.content:
            if block.type == "tool_use":
                first_val = next(iter(block.input.values()), "") if block.input else ""
                preview   = str(first_val)[:60]
                print(f"  → {block.name}({preview!r})", flush=True)
            elif block.type == "text" and block.text:
                print(block.text, flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Mock Mode — simulates the AI workflow using the real tools, no API key needed
#
# The tools (list_excel_sheets, read_excel_sheet, etc.) are called directly so
# the full data pipeline runs for real.  Only the Claude API call is skipped;
# a deterministic formatter produces the output instead.
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(val) -> float:
    """Parse a value to float, stripping $, commas, and leading +."""
    try:
        return float(str(val).replace(",", "").replace("$", "").replace("+", ""))
    except (ValueError, TypeError):
        return 0.0


def _fmt_money(val) -> str:
    """Format a number as $1,234,567 (negative → -$1,234,567)."""
    try:
        n = _safe_float(val)
        return f"-${abs(n):,.0f}" if n < 0 else f"${n:,.0f}"
    except (ValueError, TypeError):
        return str(val)


def _mock_register_client(intake_path: str) -> None:
    """Simulate Claude reading the intake form and creating a Salesforce record."""
    print(f"\n{'━' * 60}")
    print(f"  WEALTH AGENT — Client Registration  [MOCK MODE]")
    print(f"{'━' * 60}\n")

    # Step 1: list sheets
    print(f"  → list_excel_sheets({intake_path!r})", flush=True)
    sheets_result = json.loads(list_excel_sheets(intake_path))
    if "error" in sheets_result:
        sys.exit(f"Error reading {intake_path}: {sheets_result['error']}")
    sheet = sheets_result["sheets"][0]

    # Step 2: read intake form
    print(f"  → read_excel_sheet({sheet!r})", flush=True)
    rows   = json.loads(read_excel_sheet(intake_path, sheet))
    intake = {r["Field"]: r.get("Value", "") for r in rows}

    # Step 3: build beneficiary notes and call create_salesforce_contact
    bene_parts = []
    for i in ("1", "2"):
        name = intake.get(f"Beneficiary {i} Name", "")
        if name:
            rel = intake.get(f"Beneficiary {i} Rel", "")
            pct = intake.get(f"Beneficiary {i} Pct", "")
            bene_parts.append(f"{name} ({rel}) {pct}%")
    spouse = intake.get("Spouse Name", "")
    if spouse:
        bene_parts.append(f"Spouse: {spouse} DOB {intake.get('Spouse DOB','')}")

    fn = intake.get("First Name", "")
    ln = intake.get("Last Name", "")
    print(f"  → create_salesforce_contact('{fn}', '{ln}', ...)", flush=True)

    result = json.loads(create_salesforce_contact(
        first_name         = fn,
        last_name          = ln,
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

    sf_id = result.get("id", "—")

    # Step 4: print confirmation
    W = 60
    print(f"\n{'─' * W}")
    print(f"  Registration Complete")
    print(f"{'─' * W}")
    rows_out = [
        ("Salesforce ID",  sf_id),
        ("Client",         f"{fn} {ln}"),
        ("DOB",            intake.get("Date of Birth", "")),
        ("Email",          intake.get("Email", "")),
        ("Phone",          intake.get("Phone", "")),
        ("Address",        f"{intake.get('Address','')} {intake.get('City','')} {intake.get('State','')} {intake.get('ZIP','')}"),
        ("Employer",       intake.get("Employer", "")),
        ("Occupation",     intake.get("Occupation", "")),
        ("Annual Income",  _fmt_money(intake.get("Annual Income", "0"))),
        ("Net Worth",      _fmt_money(intake.get("Est. Net Worth", "0"))),
        ("Liquid Assets",  _fmt_money(intake.get("Liquid Assets", "0"))),
        ("Risk Profile",   intake.get("Risk Tolerance", "")),
        ("Goal",           intake.get("Investment Goal", "")),
        ("Horizon",        f"{intake.get('Time Horizon (yrs)','')} years"),
        ("Beneficiaries",  "  |  ".join(bene_parts) or "—"),
        ("Lead Source",    intake.get("Referral Source", "")),
        ("Status",         "Created successfully"),
    ]
    for label, value in rows_out:
        print(f"  {label:<16}  {value}")
    print(f"{'─' * W}")


def _mock_meeting_prep(client_name: str) -> None:
    """Simulate Claude gathering all sheet data and producing the one-pager."""
    print(f"\n{'━' * 60}")
    print(f"  WEALTH AGENT — Meeting Prep: {client_name}  [MOCK MODE]")
    print(f"{'━' * 60}\n")

    # Step 1: locate client file
    print(f"  → find_client_file({client_name!r})", flush=True)
    found = json.loads(find_client_file(client_name))
    if not found.get("found"):
        print("  Client not found.")
        available = found.get("available", [])
        if available:
            print(f"  Available clients: {', '.join(available)}")
        print(f"  {found.get('tip','')}")
        return

    file_path = found["path"]
    sheets    = found["sheets"]

    # Step 2: read every sheet
    data: dict = {}
    for sheet in sheets:
        print(f"  → read_excel_sheet({sheet!r})", flush=True)
        data[sheet] = json.loads(read_excel_sheet(file_path, sheet))

    # Step 3: format and print the one-pager
    print()
    print(_build_one_pager(client_name, data))


def _build_one_pager(client_name: str, data: dict) -> str:
    """Format all sheet data into a clean advisor one-pager string."""
    W     = 64
    today = datetime.now().strftime("%Y-%m-%d")

    # Pre-load all sections so computed values are available across sections
    acct_rows  = data.get("Account Summary", [])
    dc_rows    = data.get("Distributions & Contributions", [])
    tax_rows   = data.get("Tax & Realized GL", [])
    bene_rows  = data.get("Beneficiaries", [])
    alloc_rows = data.get("Allocation", [])

    # ── Derived values ────────────────────────────────────────────────────────
    total_aum = sum(_safe_float(r.get("Market Value", 0)) for r in acct_rows)

    total_contrib = sum(_safe_float(r.get("Amount ($)", 0)) for r in dc_rows
                        if _safe_float(r.get("Amount ($)", 0)) > 0)
    total_distrib = sum(_safe_float(r.get("Amount ($)", 0)) for r in dc_rows
                        if _safe_float(r.get("Amount ($)", 0)) < 0)

    tax_map: dict = {}
    if tax_rows:
        tax_map = {r.get("Category", "").strip(): _safe_float(r.get("Amount ($)", 0))
                   for r in tax_rows}

    est_taxes  = sum(v for k, v in tax_map.items() if "Est. Tax" in k)
    net_gl     = sum(v for k, v in tax_map.items() if "Realized" in k)
    qual_div   = tax_map.get("Qualified Dividends", 0.0)
    nq_div     = tax_map.get("Non-Qual Dividends",  0.0)
    interest   = tax_map.get("Interest Income",     0.0)
    total_inc  = qual_div + nq_div + interest

    drift_flags: list = []
    for r in alloc_rows:
        try:
            dval = float(r.get("Drift", "0").replace("%", "").replace("+", ""))
            if abs(dval) >= 2.0:
                drift_flags.append((r.get("Asset Class", ""), r.get("Drift", ""), dval))
        except (ValueError, AttributeError):
            pass

    rmd_rows = [r for r in dc_rows if "RMD" in r.get("Description", "")]

    # ── Builder helpers ───────────────────────────────────────────────────────
    lines: list = []

    def rule(char="─"):
        lines.append(char * W)

    def section(title):
        lines.append("")
        lines.append(title)
        rule()

    # ═══════════════════════════════════════════════════════════════════════════
    rule("═")
    lines.append(f"  MEETING PREP ONE-PAGER  [MOCK MODE]")
    lines.append(f"  {client_name}  |  Prepared: {today}")
    rule("═")

    # ── CLIENT SNAPSHOT ───────────────────────────────────────────────────────
    section("CLIENT SNAPSHOT")
    lines.append(f"  {'Name:':<16}{client_name}")
    lines.append(f"  {'Note:':<16}Full profile available in CRM / Salesforce")

    # ── ACCOUNT SUMMARY ───────────────────────────────────────────────────────
    section("ACCOUNT SUMMARY")
    if acct_rows:
        lines.append(f"  {'Account':<22} {'Acct #':<12} {'Market Value':>13}  As of")
        lines.append(f"  {'─'*22} {'─'*12} {'─'*13}  {'─'*10}")
        for r in acct_rows:
            mv = _safe_float(r.get("Market Value", 0))
            lines.append(
                f"  {r.get('Account',''):<22} {r.get('Account #',''):<12}"
                f" {_fmt_money(mv):>13}  {r.get('As of Date','')}"
            )
        lines.append(f"  {'─'*22} {'─'*12} {'─'*13}")
        lines.append(f"  {'TOTAL AUM':<22} {'':<12} {_fmt_money(total_aum):>13}")

    # ── DISTRIBUTIONS & CONTRIBUTIONS ─────────────────────────────────────────
    section("DISTRIBUTIONS & CONTRIBUTIONS (YTD)")
    if dc_rows:
        lines.append(f"  {'Date':<12} {'Type':<14} {'Account':<10} {'Amount':>12}  Description")
        lines.append(f"  {'─'*12} {'─'*14} {'─'*10} {'─'*12}  {'─'*25}")
        for r in dc_rows:
            amt  = _safe_float(r.get("Amount ($)", 0))
            sign = "+" if amt > 0 else ""
            lines.append(
                f"  {r.get('Date',''):<12} {r.get('Type',''):<14}"
                f" {r.get('Account',''):<10} {sign + _fmt_money(amt):>12}"
                f"  {r.get('Description','')}"
            )
        lines.append("")
        lines.append(f"  {'Total Contributions:':<28} {_fmt_money(total_contrib):>12}")
        lines.append(f"  {'Total Distributions:':<28} {_fmt_money(total_distrib):>12}")
        lines.append(f"  {'Net Activity:':<28} {_fmt_money(total_contrib + total_distrib):>12}")

    # ── TAX SUMMARY ───────────────────────────────────────────────────────────
    section("TAX SUMMARY (YTD)")
    if tax_rows:
        lines.append(f"  {'Estimated Tax Payments (Q1–Q4):':<38} {_fmt_money(est_taxes):>12}")
        lines.append("")
        lines.append(f"  Realized Gains / Losses:")
        lines.append(f"    {'ST Gains:':<34} {_fmt_money(tax_map.get('Realized ST Gains', 0)):>12}")
        lines.append(f"    {'LT Gains:':<34} {_fmt_money(tax_map.get('Realized LT Gains', 0)):>12}")
        lines.append(f"    {'ST Losses:':<34} {_fmt_money(tax_map.get('Realized ST Losses', 0)):>12}")
        lines.append(f"    {'LT Losses:':<34} {_fmt_money(tax_map.get('Realized LT Losses', 0)):>12}")
        lines.append(f"    {'─'*47}")
        lines.append(f"    {'Net Realized G/L:':<34} {_fmt_money(net_gl):>12}")
        lines.append("")
        lines.append(f"  Investment Income:")
        lines.append(f"    {'Qualified Dividends:':<34} {_fmt_money(qual_div):>12}")
        lines.append(f"    {'Non-Qual Dividends:':<34} {_fmt_money(nq_div):>12}")
        lines.append(f"    {'Interest Income:':<34} {_fmt_money(interest):>12}")
        lines.append(f"    {'─'*47}")
        lines.append(f"    {'Total Income:':<34} {_fmt_money(total_inc):>12}")

    # ── BENEFICIARIES ─────────────────────────────────────────────────────────
    section("BENEFICIARIES")
    if bene_rows:
        lines.append(f"  {'Name':<24} {'Relationship':<12} {'Pct':>5}  {'Account(s)':<22}  DOB")
        lines.append(f"  {'─'*24} {'─'*12} {'─'*5}  {'─'*22}  {'─'*10}")
        for r in bene_rows:
            pct = str(r.get("Pct", "")) + "%"
            lines.append(
                f"  {r.get('Name',''):<24} {r.get('Relationship',''):<12} {pct:>5}"
                f"  {r.get('Account(s)',''):<22}  {r.get('DOB','')}"
            )

    # ── ALLOCATION ────────────────────────────────────────────────────────────
    section("CURRENT ALLOCATION vs. TARGET")
    if alloc_rows:
        lines.append(f"  {'Asset Class':<24} {'Target':>7}  {'Current':>8}  {'Mkt Value':>12}  Drift")
        lines.append(f"  {'─'*24} {'─'*7}  {'─'*8}  {'─'*12}  {'─'*8}")
        for r in alloc_rows:
            tgt   = str(r.get("Target %",  ""))
            cur   = str(r.get("Current %", ""))
            mv    = _safe_float(r.get("Market Value", 0))
            drift = r.get("Drift", "")
            try:
                flag = " ◄" if abs(float(drift.replace("%","").replace("+",""))) >= 2.0 else ""
            except (ValueError, AttributeError):
                flag = ""
            lines.append(
                f"  {r.get('Asset Class',''):<24} {tgt+'%':>7}  {cur+'%':>8}"
                f"  {_fmt_money(mv):>12}  {drift}{flag}"
            )
        if drift_flags:
            lines.append(f"\n  ◄ Drift exceeds ±2% rebalancing threshold")

    # ── ADVISOR TALKING POINTS ────────────────────────────────────────────────
    section("ADVISOR TALKING POINTS")
    talking_points: list = []

    # Allocation drift — worst offenders first
    for asset_class, drift, dval in sorted(drift_flags, key=lambda x: abs(x[2]), reverse=True):
        direction = "OVERWEIGHT" if dval > 0 else "UNDERWEIGHT"
        talking_points.append(
            f"⚠  {asset_class}: {drift} ({direction}) — review rebalancing trade"
        )

    # RMD check
    for r in rmd_rows:
        amt = _safe_float(r.get("Amount ($)", 0))
        talking_points.append(
            f"→  RMD of {_fmt_money(amt)} taken {r.get('Date','')} from"
            f" {r.get('Account','')} — confirm tax withholding election on file"
        )

    # Tax G/L commentary
    if tax_rows:
        if net_gl > 0:
            talking_points.append(
                f"→  Net realized gain of {_fmt_money(net_gl)} YTD"
                f" — coordinate with CPA before year-end"
            )
        else:
            talking_points.append(
                f"→  Net realized loss of {_fmt_money(abs(net_gl))}"
                f" — assess additional TLH opportunities"
            )

    # AUM overview
    if acct_rows:
        talking_points.append(
            f"→  AUM totals {_fmt_money(total_aum)} across {len(acct_rows)} accounts"
            f" — review consolidation opportunities"
        )

    for tp in talking_points:
        lines.append(f"  {tp}")

    lines.append("")
    rule("═")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Mode: Register Client
# ─────────────────────────────────────────────────────────────────────────────

def register_client(intake_path: str, mock: bool = False) -> None:
    if not Path(intake_path).exists():
        sys.exit(
            f"File not found: {intake_path}\n"
            "Run 'python wealth_agent.py setup' to create sample data."
        )

    if mock:
        _mock_register_client(intake_path)
    else:
        _run_agent(
            system   = REGISTER_SYSTEM,
            user_msg = f"Register the new client from the intake form at: {intake_path}",
            tools    = [list_excel_sheets, read_excel_sheet, create_salesforce_contact],
            header   = "WEALTH AGENT — Client Registration",
        )

    # Print raw Salesforce record so every mapped field is visible
    MockSalesforce.print_records()


# ─────────────────────────────────────────────────────────────────────────────
# Mode: Meeting Prep One-Pager
# ─────────────────────────────────────────────────────────────────────────────

def meeting_prep(client_name: str, mock: bool = False) -> None:
    if mock:
        _mock_meeting_prep(client_name)
    else:
        _run_agent(
            system   = MEETING_PREP_SYSTEM,
            user_msg = f"Prepare a meeting one-pager for: {client_name}",
            tools    = [find_client_file, list_excel_sheets, read_excel_sheet],
            header   = f"WEALTH AGENT — Meeting Prep: {client_name}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wealth_agent.py",
        description="Wealth Management AI Agent — powered by Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Quick start (real mode):
  python wealth_agent.py setup
  python wealth_agent.py register
  python wealth_agent.py meeting-prep "Robert Thornton"

Mock mode (no API key):
  python wealth_agent.py --mock register
  python wealth_agent.py --mock meeting-prep "Robert Thornton"
""",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run without an API key using deterministic mock output",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("setup", help="Generate sample Excel data files")

    reg = sub.add_parser("register", help="Register a new client from an intake form")
    reg.add_argument(
        "--intake",
        default=str(DATA_DIR / "client_intake.xlsx"),
        metavar="PATH",
        help="Path to intake form (default: data/client_intake.xlsx)",
    )

    prep = sub.add_parser("meeting-prep", help="Generate an advisor meeting one-pager")
    prep.add_argument("client_name", help="Client full name, e.g. 'Robert Thornton'")

    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "setup":
        create_dummy_data()
        return

    if not args.mock and not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit(
            "Error: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Tip: run with --mock to test without an API key."
        )

    if args.cmd == "register":
        register_client(args.intake, mock=args.mock)
    elif args.cmd == "meeting-prep":
        meeting_prep(args.client_name, mock=args.mock)


if __name__ == "__main__":
    main()
