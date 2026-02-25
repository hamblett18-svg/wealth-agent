"""
pdf_filler.py  –  Fill IWS PDF forms with client data extracted from intake.

Uses PyMuPDF (fitz), which handles AES-encrypted PDFs natively.
"""

import io
import os
import datetime

import fitz  # pymupdf

FORMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forms")

_PERSONAL_PDF = "IWSPersonalApp_Dec2024.pdf"
_TRUST_PDF    = "IWSTrustApp_Dec2024.pdf"
_ADVISOR_PDF  = "Add_RemoveAdvisor_Brokerage_Jan2026.pdf"
_JOURNAL_PDF  = "JournalRequest_May2021_rev.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _split_name(full_name):
    """Return (first, mi, last) from a full-name string."""
    parts = (full_name or "").strip().split()
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], parts[1][0].upper(), " ".join(parts[2:])


def _parse_address(raw):
    """
    Best-effort parse of 'Street, City, ST ZIP' or similar.
    Returns (street, city, state, zipcode, country).
    """
    if not raw:
        return "", "", "", "", "USA"
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) >= 3:
        street = parts[0]
        city   = parts[1]
        st_zip = parts[2].strip().split()
        state   = st_zip[0] if st_zip else ""
        zipcode = st_zip[1] if len(st_zip) > 1 else ""
        return street, city, state, zipcode, "USA"
    if len(parts) == 2:
        return parts[0], parts[1], "", "", "USA"
    return raw, "", "", "", "USA"


def _fill(filename, fields):
    """
    Fill a PDF form using PyMuPDF and return the bytes of the filled PDF.
    Only writes fields that have a non-empty value.
    """
    path = os.path.join(FORMS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Form PDF not found at: {path}")

    doc = fitz.open(path)
    for page in doc:
        for widget in page.widgets():
            name = widget.field_name
            if name in fields and fields[name]:
                widget.field_value = str(fields[name])
                widget.update()

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Individual form fillers
# ─────────────────────────────────────────────────────────────────────────────

def fill_personal_app(client, co_client=None):
    """
    Fill IWSPersonalApp_Dec2024.pdf.

    client    – primary account holder dict
    co_client – optional second account holder dict (for joint accounts).
                Can also supply Co-Account Holder Name / Co-Account Holder DOB
                directly inside client dict.
    """
    name  = client.get("Full Name", "")
    first, mi, last = _split_name(name)
    addr  = client.get("Address", "")
    street, city, state, zipcode, country = _parse_address(addr)
    today = datetime.date.today().strftime("%m/%d/%Y")

    fields = {
        "PI_FirstName":          first,
        "PI_MI":                 mi,
        "PI_LastName":           last,
        "PI_DOB":                client.get("Date of Birth", ""),
        "PI_SSN":                client.get("SSN", client.get("Social Security Number", "")),
        "PI_PrimaryMobilePhone": client.get("Phone", client.get("Mobile Phone", "")),
        "PI_Email":              client.get("Email", ""),
        "PI_PermAddress":        street,
        "PI_PermAddressCity":    city,
        "PI_PermAddressState":   state,
        "PI_PermAddressZip":     zipcode,
        "PI_PermAddressCountry": country,
        "PI_MailingAddress":        street,
        "PI_MailingAddressCity":    city,
        "PI_MailingAddressState":   state,
        "PI_MailingAddressZip":     zipcode,
        "PI_MailingAddressCountry": country,
        "PI_EIAEmployerName": client.get("Employer", client.get("Employer Name", "")),
        "AS_Date03": today,
    }

    # Joint / co-holder info
    co_name = ""
    co_dob  = ""
    if co_client:
        co_name = co_client.get("Full Name", "")
        co_dob  = co_client.get("Date of Birth", "")
    if not co_name:
        co_name = client.get("Co-Account Holder Name", "")
        co_dob  = client.get("Co-Account Holder DOB", "")

    if co_name:
        f2, m2, l2 = _split_name(co_name)
        co_addr = (co_client or {}).get("Address", addr)
        s2, c2, st2, z2, _ = _parse_address(co_addr)
        co_phone = (co_client or {}).get("Phone", (co_client or {}).get("Mobile Phone", ""))
        co_email = (co_client or {}).get("Email", "")
        co_ssn   = (co_client or {}).get("SSN", (co_client or {}).get("Social Security Number", ""))
        fields.update({
            "PI_FirstName02":          f2,
            "PI_MI02":                 m2,
            "PI_LastName02":           l2,
            "PI_DOB02":                co_dob,
            "PI_SSN02":                co_ssn,
            "PI_PrimaryMobilePhone02": co_phone,
            "PI_Email02":              co_email,
            "PI_PermAddress02":        s2 or street,
            "PI_PermAddressCity02":    c2 or city,
            "PI_PermAddressState02":   st2 or state,
            "PI_PermAddressZip02":     z2 or zipcode,
            "PI_PermAddressCountry02": "USA",
            "PI_MailingAddress02":        s2 or street,
            "PI_MailingAddressCity02":    c2 or city,
            "PI_MailingAddressState02":   st2 or state,
            "PI_MailingAddressZip02":     z2 or zipcode,
            "PI_MailingAddressCountry02": "USA",
            "AS_Date04": today,
        })

    return _fill(_PERSONAL_PDF, fields)


def fill_trust_app(client, trustee2=None):
    """Fill IWSTrustApp_Dec2024.pdf."""
    trust_name  = client.get("Trust Name", client.get("Entity Name", client.get("Full Name", "")))
    trust_tin   = client.get("Tax ID", client.get("EIN", client.get("SSN", "")))
    trust_date  = client.get("Trust Date", client.get("Date of Trust", ""))
    trust_state = client.get("State", "")

    name  = client.get("Full Name", "")
    first, mi, last = _split_name(name)
    addr  = client.get("Address", "")
    street, city, state, zipcode, country = _parse_address(addr)
    today = datetime.date.today().strftime("%m/%d/%Y")

    fields = {
        "ASU_NameofTrust":           trust_name,
        "ASU_SSTIN":                 trust_tin,
        "ASU_DateOfTrust":           trust_date,
        "ASU_StateWhereOrganized":   trust_state or state,
        "ASU_PermanentAddress":      street,
        "ASU_PermanentAddressCity":  city,
        "ASU_PermanentAddressState": state,
        "ASU_PermanentAddressZip":   zipcode,
        "ASU_PermanentAddressCountry": country,
        # Primary trustee
        "PI_FirstName": first,
        "PI_MI":        mi,
        "PI_LastName":  last,
        "PI_DOB":   client.get("Date of Birth", ""),
        "PI_SSN":   client.get("SSN", ""),
        "PI_Email": client.get("Email", ""),
        "PI_PrimaryMobilePhone": client.get("Phone", ""),
        "PI_PermAddress":        street,
        "PI_PermAddressCity":    city,
        "PI_PermAddressState":   state,
        "PI_PermAddressZip":     zipcode,
        "PI_PermAddressCountry": country,
        "CT_Date01": today,
    }

    if trustee2:
        t2_name = trustee2.get("Full Name", "")
        f2, m2, l2 = _split_name(t2_name)
        t2_addr = trustee2.get("Address", addr)
        s2, c2, st2, z2, _ = _parse_address(t2_addr)
        fields.update({
            "PI_FirstName02": f2, "PI_MI02": m2, "PI_LastName02": l2,
            "PI_DOB02":   trustee2.get("Date of Birth", ""),
            "PI_SSN02":   trustee2.get("SSN", ""),
            "PI_Email02": trustee2.get("Email", ""),
            "PI_PrimaryMobilePhone02": trustee2.get("Phone", ""),
            "PI_PermAddress02":    s2 or street,
            "PI_PermAddressCity02":    c2 or city,
            "PI_PermAddressState02":   st2 or state,
            "PI_PermAddressZip02":     z2 or zipcode,
            "PI_PermAddressCountry02": "USA",
            "CT_Date02": today,
        })

    return _fill(_TRUST_PDF, fields)


def fill_add_remove_advisor(client, advisor_name="", advisor_gnumber="",
                             dtc_number="", pricing_code="",
                             account_numbers=None):
    """Fill Add / Remove Advisor – Brokerage form."""
    name = client.get("Full Name", "")
    first, mi, last = _split_name(name)
    today = datetime.date.today().strftime("%m/%d/%Y")
    accts = account_numbers or []

    fields = {
        "AI_First": first,
        "AI_MI":    mi,
        "AI_Last":  last,
        "DA_AdvisorName": advisor_name,
        "DA_GNumber":     advisor_gnumber,
        "DA_DTCNumber":   dtc_number,
        "DA_PricingCode": pricing_code,
        "SD_PrintAccountOwner": name,
        "SD_Date": today,
    }
    acct_keys = ["AI_Account"] + [f"AI_Account{str(i).zfill(2)}" for i in range(1, 15)]
    for i, acct in enumerate(accts[: len(acct_keys)]):
        fields[acct_keys[i]] = acct

    return _fill(_ADVISOR_PDF, fields)


def fill_journal_request(client, receiving_account="", receiving_owner="",
                          firm="IWS", gnumber=""):
    """Fill Journal / Internal Transfer Request form."""
    name = client.get("Full Name", "")
    first, mi, last = _split_name(name)
    today = datetime.date.today().strftime("%m/%d/%Y")

    fields = {
        "AO_First": first,
        "AO_MI":    mi,
        "AO_Last":  last,
        "AO_SocialSecurityNumber": client.get("SSN", client.get("Social Security Number", "")),
        "JR_FirmName": firm,
        "JR_GNumber":  gnumber,
        "RAI_OwnerName": receiving_owner or name,
        "RAI_Account":   receiving_account,
        "SaD_PrintAccountOwnerName": name,
        "SD_Date": today,
    }
    return _fill(_JOURNAL_PDF, fields)


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def fill_form(form_key, client, co_client=None, **kwargs):
    """
    Fill a form by its FORM_CATALOG key.
    Returns the filled PDF as bytes.

    form_key: 'IWSPersonalApp' | 'IWSTrustApp' | 'AddRemoveAdvisor' | 'JournalRequest'
    client:   primary client dict
    co_client: optional second holder/trustee dict
    kwargs:   passed to the specific filler (e.g. advisor_name, gnumber)
    """
    if form_key == "IWSPersonalApp":
        return fill_personal_app(client, co_client=co_client)
    elif form_key == "IWSTrustApp":
        return fill_trust_app(client, trustee2=co_client)
    elif form_key == "AddRemoveAdvisor":
        return fill_add_remove_advisor(client, **kwargs)
    elif form_key == "JournalRequest":
        return fill_journal_request(client, **kwargs)
    else:
        raise ValueError(f"Unknown form key: {form_key!r}")
