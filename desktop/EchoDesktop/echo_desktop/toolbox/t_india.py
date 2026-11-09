"""India: format checks for PAN, GSTIN, Aadhaar, IFSC, UPI and phone numbers (offline, nothing stored or sent), plus
live IFSC and PIN-code lookups. Format checks say whether a number is well-formed, not whether it's real or whose it is."""
from __future__ import annotations

import re

from . import ToolError, tool

C = "india"


@tool(C, ex={"pan": "ABCPE1234F"}, keys="pan card number valid check format")
def pan_check(pan: str) -> str:
    """Check a PAN's format and say what kind of holder it is for."""
    p = pan.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", p):
        return "Not a valid PAN format (it should look like ABCDE1234F)."
    kinds = {"P": "an individual", "C": "a company", "H": "a Hindu undivided family", "F": "a firm", "A": "an association of persons",
             "T": "a trust", "B": "a body of individuals", "L": "a local authority", "J": "an artificial juridical person", "G": "a government body"}
    return f"Valid PAN format, issued to {kinds.get(p[3], 'an unknown holder type')}."


GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
STATES = {"01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
          "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
          "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
          "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
          "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar",
          "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh"}


def gst_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = GST_CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return GST_CHARS[(36 - total % 36) % 36]


@tool(C, ex={"gstin": "27AAPFU0939F1ZV"}, keys="gst number gstin valid check business")
def gstin_check(gstin: str) -> str:
    """Check a GSTIN's format and checksum, and name its state."""
    g = gstin.strip().upper()
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", g):
        return "Not a valid GSTIN format (15 characters like 27AAPFU0939F1ZV)."
    if gst_check_char(g[:14]) != g[14]:
        return "The format looks right but the check character is wrong — probably a typo."
    return f"Valid GSTIN for {STATES.get(g[:2], 'an unknown state code')} (PAN {g[2:12]})."


_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
      [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1], [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
      [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
      [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1], [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, d in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(d)]]
    return c == 0


@tool(C, keys="aadhaar number valid check typo format")
def aadhaar_format_check(number: str) -> str:
    """Check whether a 12-digit Aadhaar number is well-formed (catches typos). Offline; the number isn't stored or sent."""
    n = re.sub(r"\s|-", "", number)
    if not re.fullmatch(r"[2-9]\d{11}", n):
        return "Not a valid Aadhaar format (12 digits, not starting with 0 or 1)."
    return "Well-formed Aadhaar number." if verhoeff_ok(n) else "The check digit doesn't match — probably a typo."


@tool(C, ex={"ifsc": "SBIN0000691"}, keys="ifsc code bank branch valid format")
def ifsc_format_check(ifsc: str) -> str:
    """Check an IFSC code's format and name the bank code."""
    i = ifsc.strip().upper()
    if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", i):
        return "Not a valid IFSC format (11 characters like SBIN0000691)."
    return f"Valid IFSC format: bank code {i[:4]}, branch code {i[5:]}."


@tool(C, ex={"ifsc": "SBIN0000691"}, net=True, keys="ifsc bank branch address lookup details")
def ifsc_lookup(ifsc: str) -> str:
    """Bank, branch and address for an IFSC code (live)."""
    from .. import internet
    try:
        d = internet.get_json("https://ifsc.razorpay.com/" + ifsc.strip().upper(), 86400)
    except internet.NetError:
        raise ToolError("that IFSC wasn't found")
    return f"{d.get('BANK')}, {d.get('BRANCH')} branch: {d.get('ADDRESS')}, {d.get('CITY')}, {d.get('STATE')}. UPI {'yes' if d.get('UPI') else 'no'}, NEFT {'yes' if d.get('NEFT') else 'no'}."


@tool(C, ex={"pincode": "520001"}, net=True, keys="pin code post office area lookup postal")
def pincode_lookup(pincode: str) -> str:
    """Post offices, district and state for an Indian PIN code (live)."""
    from .. import internet
    p = re.sub(r"\D", "", pincode)
    if len(p) != 6:
        raise ToolError("a PIN code has 6 digits")
    d = internet.get_json("https://api.postalpincode.in/pincode/" + p, 86400)
    offices = (d[0].get("PostOffice") or []) if d else []
    if not offices:
        raise ToolError("that PIN code wasn't found")
    o = offices[0]
    return f"{p}: {o.get('District')}, {o.get('State')}. Post offices: " + ", ".join(x["Name"] for x in offices[:8]) + "."


@tool(C, ex={"upi_id": "asha@okaxis"}, keys="upi id vpa valid format")
def upi_id_check(upi_id: str) -> str:
    """Check a UPI ID's format (name@bank). Reminder: you never need your PIN to receive money."""
    ok = re.fullmatch(r"[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}", upi_id.strip())
    return ("Valid UPI ID format." if ok else "Not a valid UPI ID format (it looks like name@bank).") + " Never enter your UPI PIN to receive money."


@tool(C, ex={"number": "+91 98765 43210"}, keys="mobile phone number valid indian format")
def indian_mobile_check(number: str) -> str:
    """Check an Indian mobile number's format and tidy it."""
    n = re.sub(r"\D", "", number)
    if n.startswith("91") and len(n) == 12:
        n = n[2:]
    if n.startswith("0") and len(n) == 11:
        n = n[1:]
    if not re.fullmatch(r"[6-9]\d{9}", n):
        return "Not a valid Indian mobile number (10 digits starting with 6–9)."
    return f"Valid: +91 {n[:5]} {n[5:]}."


@tool(C, ex={"amount": 12550000.75}, keys="lakh crore rupees words amount cheque")
def rupees_in_words(amount: float) -> str:
    """Amount in Indian words, as on a cheque ('One crore twenty-five lakh … rupees and seventy-five paise only')."""
    from .t_math import number_words
    r, p = int(amount), round((amount - int(amount)) * 100)
    out = number_words(r, "indian").capitalize() + " rupees"
    if p:
        out += f" and {number_words(p)} paise"
    return out + " only"


@tool(C, ex={"plate": "AP 39 AB 1234"}, keys="vehicle registration number plate state rto")
def vehicle_number_check(plate: str) -> str:
    """Check a vehicle registration number's format and name its state."""
    codes = {"AP": "Andhra Pradesh", "TS": "Telangana", "TG": "Telangana", "KA": "Karnataka", "TN": "Tamil Nadu", "KL": "Kerala", "MH": "Maharashtra",
             "DL": "Delhi", "UP": "Uttar Pradesh", "GJ": "Gujarat", "RJ": "Rajasthan", "WB": "West Bengal", "MP": "Madhya Pradesh", "HR": "Haryana",
             "PB": "Punjab", "BR": "Bihar", "OD": "Odisha", "OR": "Odisha", "AS": "Assam", "GA": "Goa", "JK": "Jammu & Kashmir", "UK": "Uttarakhand",
             "HP": "Himachal Pradesh", "CG": "Chhattisgarh", "JH": "Jharkhand", "CH": "Chandigarh", "PY": "Puducherry"}
    p = re.sub(r"[\s-]", "", plate.upper())
    if re.fullmatch(r"\d{2}BH\d{4}[A-Z]{1,2}", p):
        return "Valid Bharat-series (BH) number — usable in any state."
    m = re.fullmatch(r"([A-Z]{2})(\d{1,2})([A-Z]{0,3})(\d{1,4})", p)
    if not m:
        return "Not a standard registration number format."
    return f"Valid format: {codes.get(m.group(1), 'unknown state code ' + m.group(1))}, RTO {m.group(2)}."
