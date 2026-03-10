"""
GST Parser — Parse GSTR-1 and GSTR-3B PDFs into 24-month monthly data.

Handles:
  - Digital GSTR-3B PDFs (government portal format)
  - Digital GSTR-1 PDFs
  - Scanned GST returns (OCR fallback via EasyOCR)
  - GSTIN format validation (22AAAAA0000A1Z5)
  - GSTR-3B table headers: "Outward Taxable Supplies", "ITC Available", "Tax Paid"
  - ITC mismatch / filing gap / turnover discrepancy detection

Stores results in gst_monthly_data Supabase table.
"""

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import fitz  # PyMuPDF

from services.supabase_client import get_supabase


# ═══════════════════════════════════════════════════════════════════════════
# Indian GST-specific constants
# ═══════════════════════════════════════════════════════════════════════════

# GSTIN format: 2-digit state code + 10-char PAN + 1 entity + 1 checksum + Z
GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d][Z][A-Z\d])\b")

# GSTR-3B table section headers (official government format)
_3B_SECTIONS = {
    "outward_taxable": [
        r"3\.1.*outward\s*taxable\s*supplies",
        r"outward\s*taxable\s*supplies",
        r"table\s*3\.1",
        r"details\s*of\s*outward\s*supplies",
    ],
    "itc_available": [
        r"4\..*eligible\s*itc",
        r"itc\s*available",
        r"input\s*tax\s*credit",
        r"table\s*4",
        r"details\s*of.*itc\s*as\s*per",
    ],
    "itc_reversed": [
        r"4\..*itc\s*reversed",
        r"itc\s*reversal",
        r"reversal\s*of\s*itc",
    ],
    "tax_paid": [
        r"6\..*tax\s*(?:paid|payable)",
        r"payment\s*of\s*tax",
        r"table\s*6",
        r"tax\s*payable",
    ],
    "interest_late_fee": [
        r"5\.1.*interest\s*(?:and|&)\s*late\s*fee",
        r"interest.*late\s*fee",
        r"late\s*fee\s*payable",
    ],
}

# GSTR-1 section headers
_1_SECTIONS = {
    "b2b": [
        r"4A.*B2B\s*invoices?",
        r"B2B\s*(?:invoices?|supplies)",
        r"table\s*4A",
    ],
    "b2c_large": [
        r"5A.*B2C\s*\(Large\)",
        r"B2C\s*large",
    ],
    "b2c_small": [
        r"7.*B2C\s*\(Others\)",
        r"B2C\s*(?:others?|small)",
    ],
    "exports": [
        r"6A.*exports?",
        r"export\s*invoices?",
    ],
    "credit_debit_notes": [
        r"9B.*credit.*debit\s*notes?",
        r"credit\s*/\s*debit\s*notes?",
    ],
}

# GST tax heads
_TAX_HEADS = ["igst", "cgst", "sgst", "cess"]


# ═══════════════════════════════════════════════════════════════════════════
# Month helpers
# ═══════════════════════════════════════════════════════════════════════════

_MONTH_NAMES = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}

# Indian financial month mapping for GST periods
_GST_PERIOD_RE = re.compile(
    r"(?:(?:for\s*(?:the\s*)?)?(?:month|period)\s*(?:of|:)\s*)?"
    r"([A-Za-z]+)\s*[-,/]?\s*(\d{4})",
    re.IGNORECASE,
)
_GST_PERIOD_NUM_RE = re.compile(r"(\d{2})[/-](\d{4})")
_GST_RETURN_PERIOD_RE = re.compile(r"Return\s*Period\s*[:\-]?\s*([A-Za-z]+)\s*[-,]?\s*(\d{4})", re.IGNORECASE)


def _normalize_month(raw: str) -> Optional[str]:
    """Convert various month representations to YYYY-MM."""
    raw = raw.strip()

    # YYYY-MM
    m = re.match(r"^(\d{4})-(\d{2})$", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # MM-YYYY or MM/YYYY
    m = re.match(r"^(\d{2})[-/](\d{4})$", raw)
    if m:
        return f"{m.group(2)}-{m.group(1)}"

    # Month-name Year (various)
    m = re.match(r"([a-zA-Z]+)\s*[-,./]?\s*(\d{4})", raw)
    if m:
        month_str = m.group(1).lower()
        mm = _MONTH_NAMES.get(month_str)
        if mm:
            return f"{m.group(2)}-{mm}"

    return None


def _detect_return_period(text: str) -> Optional[str]:
    """Detect the return period from GSTR header text."""
    # "Return Period: January 2024" format
    m = _GST_RETURN_PERIOD_RE.search(text)
    if m:
        month_str = m.group(1).lower()
        mm = _MONTH_NAMES.get(month_str)
        if mm:
            return f"{m.group(2)}-{mm}"

    # Fallback: any month-year pattern near top of document
    for m in _GST_PERIOD_RE.finditer(text[:2000]):
        month_str = m.group(1).lower()
        mm = _MONTH_NAMES.get(month_str)
        if mm:
            return f"{m.group(2)}-{mm}"

    m = _GST_PERIOD_NUM_RE.search(text[:2000])
    if m:
        return f"{m.group(2)}-{m.group(1)}"

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Number parsing
# ═══════════════════════════════════════════════════════════════════════════

_STRIP_RE = re.compile(r"[₹$,\s\u00a0]")


def _parse_amount(raw: str) -> Optional[float]:
    """Parse Indian-format currency to float."""
    if not raw:
        return None
    cleaned = _STRIP_RE.sub("", str(raw)).strip()
    if not cleaned or cleaned in {"-", "–", "—", "NA", "N/A", "nil", "Nil", "0.00"}:
        return 0.0

    neg = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        neg = True
        cleaned = cleaned[1:-1]
    elif cleaned.startswith("-") or cleaned.startswith("−"):
        neg = True
        cleaned = cleaned[1:]

    try:
        val = float(cleaned)
        return -val if neg else val
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# PDF text extraction
# ═══════════════════════════════════════════════════════════════════════════

def _extract_pdf_text(file_path: str) -> str:
    """Extract full text from PDF using PyMuPDF."""
    text_parts = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text_parts.append(page.get_text("text"))
        doc.close()
    except Exception as exc:
        print(f"[GSTParser] PyMuPDF extraction failed: {exc}")
    return "\n".join(text_parts)


def _extract_with_ocr(file_path: str) -> str:
    """Fallback: OCR for scanned GST returns using EasyOCR."""
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        # Convert PDF pages to images first
        doc = fitz.open(file_path)
        all_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            img_path = f"/tmp/gst_page_{page_num}.png"
            pix.save(img_path)
            results = reader.readtext(img_path)
            page_text = " ".join([r[1] for r in results])
            all_text.append(page_text)
        doc.close()
        return "\n".join(all_text)
    except ImportError:
        print("[GSTParser] EasyOCR not available for scanned PDF fallback")
        return ""
    except Exception as exc:
        print(f"[GSTParser] OCR fallback failed: {exc}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# GSTIN extraction & validation
# ═══════════════════════════════════════════════════════════════════════════

def _extract_gstin(text: str) -> Optional[str]:
    """Extract and validate GSTIN from text."""
    m = GSTIN_RE.search(text)
    if m:
        gstin = m.group(1)
        # Basic validation: state code 01-37, valid PAN structure
        state_code = int(gstin[:2])
        if 1 <= state_code <= 37:
            return gstin
    return None


def _extract_pan_from_gstin(gstin: str) -> str:
    """Extract PAN from GSTIN (characters 2-12)."""
    return gstin[2:12] if len(gstin) >= 12 else ""


# ═══════════════════════════════════════════════════════════════════════════
# GSTR-3B parsing (government format)
# ═══════════════════════════════════════════════════════════════════════════

def _find_section_value(text: str, section_patterns: List[str]) -> Optional[float]:
    """Find a section header and extract the first numeric value after it."""
    for pattern in section_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            # Get text after the match (next ~500 chars)
            after = text[m.end():m.end() + 500]
            # Find first significant number
            nums = re.findall(r"[\d,]+\.?\d*", after)
            for n in nums:
                val = _parse_amount(n)
                if val is not None and val > 0:
                    return val
    return None


def _parse_gstr3b_document(text: str, file_path: str) -> Dict[str, Any]:
    """
    Parse a single GSTR-3B document.
    Extracts: return period, GSTIN, outward taxable supplies, ITC, tax paid.
    """
    result: Dict[str, Any] = {}

    # Return period
    period = _detect_return_period(text)
    result["month"] = period

    # GSTIN
    gstin = _extract_gstin(text)
    result["gstin"] = gstin

    # 3.1 — Outward Taxable Supplies (this is the turnover)
    turnover = _find_section_value(text, _3B_SECTIONS["outward_taxable"])
    result["gstr3b_turnover"] = turnover or 0

    # 4 — ITC Available
    itc_available = _find_section_value(text, _3B_SECTIONS["itc_available"])
    result["itc_available"] = itc_available or 0

    # 4 — ITC Reversed
    itc_reversed = _find_section_value(text, _3B_SECTIONS["itc_reversed"])
    result["itc_reversal"] = itc_reversed or 0

    # Net ITC claimed = available - reversed
    result["itc_claimed"] = (result["itc_available"] or 0) - (result["itc_reversal"] or 0)

    # 6 — Tax Paid
    tax_paid = _find_section_value(text, _3B_SECTIONS["tax_paid"])
    result["tax_paid"] = tax_paid or 0

    # Interest / Late fee
    late_fee = _find_section_value(text, _3B_SECTIONS["interest_late_fee"])
    result["late_fee"] = late_fee or 0

    # Filing status
    result["filing_status"] = "filed" if turnover is not None else "missing"

    return result


def _parse_gstr3b_multi_month(text: str) -> List[Dict[str, Any]]:
    """
    Parse GSTR-3B that contains multiple months of data
    (e.g., annual summary or consolidated download).
    """
    rows: List[Dict[str, Any]] = []
    lines = text.split("\n")
    current_month = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect month headers
        month = _normalize_month(line)
        if month:
            current_month = month
            continue

        # Also check for "Return Period: Month Year" pattern
        m = _GST_RETURN_PERIOD_RE.search(line)
        if m:
            ms = m.group(1).lower()
            mm = _MONTH_NAMES.get(ms)
            if mm:
                current_month = f"{m.group(2)}-{mm}"
                continue

        if current_month:
            # Try to find numeric data
            numbers = re.findall(r"[\d,]+\.?\d*", line)
            if len(numbers) >= 2:
                values = [_parse_amount(n) for n in numbers]
                values = [v for v in values if v is not None]
                if len(values) >= 2:
                    row = {
                        "month": current_month,
                        "gstr3b_turnover": values[0] if len(values) > 0 else 0,
                        "tax_paid": values[1] if len(values) > 1 else 0,
                        "itc_claimed": values[2] if len(values) > 2 else 0,
                        "itc_available": values[3] if len(values) > 3 else 0,
                        "itc_reversal": 0,
                        "late_fee": values[4] if len(values) > 4 else 0,
                        "filing_status": "filed",
                    }
                    if not any(r["month"] == current_month for r in rows):
                        rows.append(row)
                    current_month = None

    return rows


# ═══════════════════════════════════════════════════════════════════════════
# GSTR-1 parsing
# ═══════════════════════════════════════════════════════════════════════════

def _parse_gstr1_document(text: str) -> Dict[str, Any]:
    """
    Parse a GSTR-1 (outward supplies) document.
    Extracts: total taxable value from B2B + B2C summaries.
    """
    result: Dict[str, Any] = {}

    period = _detect_return_period(text)
    result["month"] = period
    result["gstin"] = _extract_gstin(text)

    # Sum B2B + B2C taxable values for total turnover
    total_turnover = 0.0

    b2b_val = _find_section_value(text, _1_SECTIONS["b2b"])
    if b2b_val:
        total_turnover += b2b_val

    b2c_large = _find_section_value(text, _1_SECTIONS["b2c_large"])
    if b2c_large:
        total_turnover += b2c_large

    b2c_small = _find_section_value(text, _1_SECTIONS["b2c_small"])
    if b2c_small:
        total_turnover += b2c_small

    exports = _find_section_value(text, _1_SECTIONS["exports"])
    if exports:
        total_turnover += exports

    # If no section-level extraction, try total line
    if total_turnover == 0:
        total_turnover = _find_section_value(text, [
            r"total\s*taxable\s*value",
            r"total\s*turnover",
            r"aggregate\s*turnover",
        ]) or 0

    result["gstr1_turnover"] = total_turnover
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Merge + anomaly detection
# ═══════════════════════════════════════════════════════════════════════════

def _merge_gst_data(
    gstr3b: List[Dict], gstr1: List[Dict]
) -> List[Dict[str, Any]]:
    """Merge GSTR-3B and GSTR-1 data by month."""
    by_month: Dict[str, Dict[str, Any]] = {}

    for row in gstr3b:
        m = row.get("month")
        if not m:
            continue
        by_month.setdefault(m, {"month": m})
        by_month[m].update(row)

    for row in gstr1:
        m = row.get("month")
        if not m:
            continue
        by_month.setdefault(m, {"month": m})
        by_month[m]["gstr1_turnover"] = row.get("gstr1_turnover", 0)

    merged = sorted(by_month.values(), key=lambda x: x["month"])

    # Ensure all fields have defaults
    for row in merged:
        row.setdefault("gstr3b_turnover", 0)
        row.setdefault("gstr1_turnover", 0)
        row.setdefault("itc_claimed", 0)
        row.setdefault("itc_available", 0)
        row.setdefault("itc_reversal", 0)
        row.setdefault("tax_paid", 0)
        row.setdefault("mismatch_amount", 0)
        row.setdefault("late_fee", 0)
        row.setdefault("filing_status", "filed")

    return merged


def _detect_anomalies(monthly_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect GST anomalies:
    - ITC mismatch (claimed > available × 1.2)
    - Filing gaps (missing months in 24-month window)
    - Turnover discrepancy (GSTR-3B vs GSTR-1 > 20%)
    - Sudden turnover spikes/drops (>50% month-over-month)
    - Late fees indicating delayed filing
    """
    flags: List[Dict[str, Any]] = []

    prev_turnover: Optional[float] = None

    for row in monthly_data:
        month = row.get("month", "unknown")

        # ITC mismatch
        itc_claimed = float(row.get("itc_claimed") or 0)
        itc_available = float(row.get("itc_available") or 0)
        if itc_available > 0 and itc_claimed > itc_available * 1.2:
            row["itc_reversal"] = max(row.get("itc_reversal", 0), itc_claimed - itc_available)
            flags.append({
                "month": month, "type": "itc_mismatch",
                "severity": "high",
                "detail": f"ITC claimed (₹{itc_claimed:,.0f}) exceeds 1.2× available (₹{itc_available:,.0f})",
            })

        # Turnover mismatch (3B vs 1)
        t3b = float(row.get("gstr3b_turnover") or 0)
        t1 = float(row.get("gstr1_turnover") or 0)
        if t3b > 0 and t1 > 0:
            mismatch_pct = abs(t3b - t1) / t3b
            row["mismatch_amount"] = abs(t3b - t1)
            if mismatch_pct > 0.2:
                severity = "critical" if mismatch_pct > 0.4 else "high"
                flags.append({
                    "month": month, "type": "turnover_mismatch",
                    "severity": severity,
                    "detail": f"GSTR-3B (₹{t3b:,.0f}) vs GSTR-1 (₹{t1:,.0f}) = {mismatch_pct*100:.1f}% mismatch",
                })

        # Sudden turnover spike/drop
        current_turnover = t3b or t1
        if prev_turnover and prev_turnover > 0 and current_turnover > 0:
            change = (current_turnover - prev_turnover) / prev_turnover
            if abs(change) > 0.5:
                direction = "spike" if change > 0 else "drop"
                flags.append({
                    "month": month, "type": f"turnover_{direction}",
                    "severity": "medium",
                    "detail": f"Turnover {direction}: {change*100:+.1f}% month-over-month",
                })
        prev_turnover = current_turnover

        # Late fee indicates delayed filing
        late_fee = float(row.get("late_fee") or 0)
        if late_fee > 0:
            flags.append({
                "month": month, "type": "late_filing",
                "severity": "low",
                "detail": f"Late fee of ₹{late_fee:,.0f} — indicates delayed filing",
            })

    # Filing gaps
    if monthly_data:
        months_present = sorted({r["month"] for r in monthly_data if r.get("month")})
        if len(months_present) < 24:
            gap_count = 24 - len(months_present)
            flags.append({
                "month": "all", "type": "filing_gap",
                "severity": "medium" if gap_count <= 3 else "high",
                "detail": f"Only {len(months_present)}/24 months filed ({gap_count} gaps)",
            })

    return flags


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

async def parse_gst_returns(
    file_paths: List[Dict[str, str]],
    application_id: str,
) -> Dict[str, Any]:
    """
    Parse GSTR-1 and GSTR-3B PDF files into 24-month monthly data.

    Handles:
    - Digital PDFs (PyMuPDF text extraction)
    - Scanned PDFs (EasyOCR fallback)
    - GSTIN extraction & PAN cross-reference
    - Per-section parsing matching official government GSTR formats
    - ITC mismatch, filing gap, turnover discrepancy detection

    Args:
        file_paths: [{"file_path": ..., "return_type": "gstr3b"|"gstr1", "document_id": ...}]
        application_id: loan application ID

    Stores each month in gst_monthly_data Supabase table.
    """
    all_3b: List[Dict] = []
    all_1: List[Dict] = []
    extracted_gstins: set = set()

    for entry in file_paths:
        fpath = entry["file_path"]
        rtype = entry.get("return_type", "gstr3b")

        # Primary: PyMuPDF
        text = _extract_pdf_text(fpath)

        # If very little text extracted, try OCR for scanned PDFs
        if len(text.strip()) < 100:
            print(f"[GSTParser] Low text content — attempting OCR on {fpath}")
            ocr_text = _extract_with_ocr(fpath)
            if len(ocr_text) > len(text):
                text = ocr_text

        # Extract GSTIN
        gstin = _extract_gstin(text)
        if gstin:
            extracted_gstins.add(gstin)

        if rtype == "gstr3b":
            # Try single-return parsing first
            single = _parse_gstr3b_document(text, fpath)
            if single.get("month") and single.get("gstr3b_turnover", 0) > 0:
                all_3b.append(single)
            else:
                # Try multi-month extraction
                multi = _parse_gstr3b_multi_month(text)
                all_3b.extend(multi)

        elif rtype == "gstr1":
            single = _parse_gstr1_document(text)
            if single.get("month"):
                all_1.append(single)

    # Merge by month
    monthly_data = _merge_gst_data(all_3b, all_1)

    # Detect anomalies
    flags = _detect_anomalies(monthly_data)

    # Store in Supabase
    try:
        supabase = get_supabase()
        for row in monthly_data:
            record = {
                "id": str(uuid.uuid4()),
                "application_id": application_id,
                "month": row["month"],
                "gstr3b_turnover": row.get("gstr3b_turnover"),
                "gstr1_turnover": row.get("gstr1_turnover"),
                "itc_claimed": row.get("itc_claimed"),
                "itc_available": row.get("itc_available"),
                "itc_reversal": row.get("itc_reversal"),
                "tax_paid": row.get("tax_paid"),
                "filing_status": row.get("filing_status", "filed"),
                "mismatch_amount": row.get("mismatch_amount"),
                "late_fee": row.get("late_fee"),
                "source_document_id": file_paths[0].get("document_id") if file_paths else None,
            }
            supabase.table("gst_monthly_data").insert(record).execute()
        print(f"[GSTParser] ✓ Stored {len(monthly_data)} months of GST data")
    except Exception as exc:
        print(f"[GSTParser] ✗ DB insert failed: {exc}")

    return {
        "application_id": application_id,
        "months_parsed": len(monthly_data),
        "monthly_data": monthly_data,
        "gstins_found": list(extracted_gstins),
        "pans_from_gstin": [_extract_pan_from_gstin(g) for g in extracted_gstins],
        "flags": flags,
        "total_flags": len(flags),
        "filing_gaps": sum(1 for f in flags if f["type"] == "filing_gap"),
        "itc_mismatches": sum(1 for f in flags if f["type"] == "itc_mismatch"),
        "turnover_mismatches": sum(1 for f in flags if f["type"] == "turnover_mismatch"),
        "late_filings": sum(1 for f in flags if f["type"] == "late_filing"),
    }


async def cross_validate_gst(
    gst_data: List[Dict],
    bank_data: List[Dict],
) -> Dict[str, Any]:
    """
    Cross-validate GST data against bank statement credits.
    Flags when bank credits diverge significantly from GST turnover.
    """
    flags = []
    gst_by_month = {r["month"]: r for r in gst_data}
    bank_by_month = {r["month"]: r for r in bank_data}

    for month, gst_row in gst_by_month.items():
        bank_row = bank_by_month.get(month)
        if not bank_row:
            continue

        gst_turnover = float(gst_row.get("gstr3b_turnover") or 0)
        bank_credits = float(bank_row.get("total_credits") or 0)

        if gst_turnover > 0:
            ratio = bank_credits / gst_turnover
            if ratio < 0.6:
                flags.append({
                    "month": month, "type": "bank_gst_low",
                    "severity": "medium",
                    "detail": f"Bank credits (₹{bank_credits:,.0f}) only {ratio:.2f}× GST turnover (₹{gst_turnover:,.0f})",
                })
            elif ratio > 1.8:
                flags.append({
                    "month": month, "type": "bank_gst_high",
                    "severity": "high",
                    "detail": f"Bank credits (₹{bank_credits:,.0f}) = {ratio:.2f}× GST turnover (₹{gst_turnover:,.0f})",
                })

    return {
        "cross_validation_flags": flags,
        "total_flags": len(flags),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Test Utility
# ═══════════════════════════════════════════════════════════════════════════

def test_parser(pdf_path: str, return_type: str = "gstr3b") -> None:
    """
    Quick test: parse a GST return PDF and print extracted values.
    Usage: python -c "from parsers.gst_parser import test_parser; test_parser('path/to/gstr3b.pdf')"
    """
    import asyncio

    async def _run():
        result = await parse_gst_returns(
            file_paths=[{"file_path": pdf_path, "return_type": return_type}],
            application_id="test-000",
        )

        print("=" * 70)
        print(f"📄 GST Parser Test — {pdf_path} ({return_type})")
        print(f"   Months parsed: {result['months_parsed']}")
        print(f"   GSTINs found:  {result['gstins_found']}")
        print(f"   Total flags:   {result['total_flags']}")
        print("=" * 70)

        for row in result.get("monthly_data", []):
            print(f"\n  {row['month']} [{row.get('filing_status', '?')}]")
            print(f"    GSTR-3B Turnover: ₹{float(row.get('gstr3b_turnover') or 0):>15,.2f}")
            print(f"    GSTR-1 Turnover:  ₹{float(row.get('gstr1_turnover') or 0):>15,.2f}")
            print(f"    ITC Available:    ₹{float(row.get('itc_available') or 0):>15,.2f}")
            print(f"    ITC Claimed:      ₹{float(row.get('itc_claimed') or 0):>15,.2f}")
            print(f"    Tax Paid:         ₹{float(row.get('tax_paid') or 0):>15,.2f}")
            mismatch = float(row.get("mismatch_amount") or 0)
            if mismatch > 0:
                print(f"    ⚠ Mismatch:       ₹{mismatch:>15,.2f}")

        if result["flags"]:
            print(f"\n{'─' * 70}")
            print("  Flags:")
            for f in result["flags"]:
                print(f"    [{f['severity'].upper():8s}] {f['month']:10s} — {f['type']}: {f['detail']}")

        print("\n" + "=" * 70)

    asyncio.run(_run())
