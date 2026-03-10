"""
Financial Parser — Extract P&L, Balance Sheet, Cash Flow, ratios from Indian PDFs.

Primary:  Docling (IBM) for structured table extraction (94%+ accuracy)
Fallback: PyMuPDF (fitz) for text-based regex extraction

Handles:
  - CA-certified Indian financial statements (Schedule III format)
  - Standalone AND consolidated balance sheets
  - Multi-year extraction from a single PDF (FY24/FY23/FY22 columns)
  - Confidence scoring with anomaly flags
  - Dynamic benchmarks from sector_benchmarks Supabase table
  - GST-aware extraction from financial statement annexures

Stores results in extracted_financials Supabase table.
"""

import re
import uuid
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import fitz  # PyMuPDF

try:
    from services.supabase_client import get_supabase
except ImportError:
    get_supabase = None  # Allow standalone testing without Supabase

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Indian Financial Statement Keywords (Schedule III / CA-certified)
# ═══════════════════════════════════════════════════════════════════════════

# P&L line items — ordered by priority
_PNL_PATTERNS: Dict[str, List[str]] = {
    "revenue_from_operations": [
        r"revenue\s*from\s*operations",
        r"income\s*from\s*operations",
        r"net\s*sales",
        r"sales\s*revenue",
        r"gross\s*revenue",
    ],
    "other_income": [
        r"other\s*income",
        r"non[\s-]*operating\s*income",
    ],
    "total_revenue": [
        r"total\s*income",
        r"total\s*revenue",
        r"gross\s*total\s*income",
    ],
    "cost_of_materials": [
        r"cost\s*of\s*materials?\s*consumed",
        r"cost\s*of\s*goods\s*sold",
        r"raw\s*materials?\s*consumed",
        r"purchases?\s*of\s*stock[\s-]*in[\s-]*trade",
    ],
    "employee_benefit_expense": [
        r"employee\s*benefit\s*expense",
        r"staff\s*cost",
        r"salaries?\s*(?:and|&)\s*wages?",
    ],
    "depreciation": [
        r"depreciation\s*(?:and|&)\s*amortis[sz]ation",
        r"depreciation\s*expense",
    ],
    "finance_cost": [
        r"finance\s*cost",
        r"interest\s*expense",
        r"interest\s*(?:and|&)\s*finance\s*charges?",
    ],
    "total_expenses": [
        r"total\s*expenses?",
    ],
    "profit_before_tax": [
        r"profit\s*before\s*(?:tax|taxation)",
        r"PBT",
        r"income\s*before\s*tax",
    ],
    "tax_expense": [
        r"tax\s*expense",
        r"income\s*tax\s*expense",
        r"provision\s*for\s*tax",
    ],
    "profit_after_tax": [
        r"profit\s*(?:after\s*tax|for\s*the\s*(?:year|period))",
        r"PAT",
        r"net\s*profit",
        r"net\s*income",
        r"profit\s*/\s*\(loss\)\s*for\s*the\s*(?:year|period)",
    ],
    "ebitda": [
        r"EBITDA",
        r"operating\s*profit\s*(?:before|bef|b/?f)\s*(?:dep|depreciation)",
        r"earnings?\s*before\s*interest",
    ],
}

# Balance Sheet line items
_BS_PATTERNS: Dict[str, List[str]] = {
    "share_capital": [
        r"share\s*capital",
        r"equity\s*share\s*capital",
        r"paid[\s-]*up\s*capital",
    ],
    "reserves_surplus": [
        r"reserves?\s*(?:and|&)\s*surplus",
        r"retained\s*earnings?",
        r"other\s*equity",
    ],
    "net_worth": [
        r"net\s*worth",
        r"shareholders?\s*(?:equity|funds?)",
        r"total\s*equity",
        r"equity\s*attributable",
    ],
    "long_term_borrowings": [
        r"long[\s-]*term\s*borrowings?",
        r"non[\s-]*current\s*(?:financial\s*)?liabilities",
        r"secured\s*loans?",
    ],
    "short_term_borrowings": [
        r"short[\s-]*term\s*borrowings?",
        r"current\s*borrowings?",
        r"working\s*capital\s*loans?",
    ],
    "total_debt": [
        r"total\s*(?:debt|borrowings?)",
    ],
    "current_assets": [
        r"total\s*current\s*assets",
        r"current\s*assets",
    ],
    "current_liabilities": [
        r"total\s*current\s*liabilities",
        r"current\s*liabilities",
    ],
    "total_assets": [
        r"total\s*assets",
    ],
    "total_liabilities": [
        r"total\s*(?:liabilities\s*(?:and|&)\s*equity|equity\s*(?:and|&)\s*liabilities)",
        r"total\s*liabilities",
    ],
    "fixed_assets": [
        r"(?:property|fixed)\s*(?:plant|assets?)\s*(?:and|&)\s*equipment",
        r"total\s*(?:non[\s-]*current|fixed)\s*assets",
    ],
    "inventories": [
        r"inventor(?:y|ies)",
    ],
    "trade_receivables": [
        r"trade\s*receivables?",
        r"sundry\s*debtors?",
    ],
    "trade_payables": [
        r"trade\s*payables?",
        r"sundry\s*creditors?",
    ],
    "cash_and_equivalents": [
        r"cash\s*(?:and|&)\s*cash\s*equivalents?",
        r"cash\s*(?:and|&)\s*bank\s*balances?",
    ],
}

# Cash Flow line items
_CF_PATTERNS: Dict[str, List[str]] = {
    "cfo": [
        r"(?:net\s*)?cash\s*(?:from|generated\s*from|used\s*in)\s*operating\s*activities",
        r"cash\s*flow\s*from\s*operations?",
        r"operating\s*cash\s*flow",
    ],
    "cfi": [
        r"(?:net\s*)?cash\s*(?:from|used\s*in)\s*investing\s*activities",
    ],
    "cff": [
        r"(?:net\s*)?cash\s*(?:from|used\s*in)\s*financing\s*activities",
    ],
}

# ═══════════════════════════════════════════════════════════════════════════
# Indian GST-specific patterns (for financial statements with GST annexures)
# ═══════════════════════════════════════════════════════════════════════════

# GSTIN: 2-digit state code + 10-char PAN + entity code + Z + check digit
_GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d][Z][A-Z\d])\b")

_GST_PATTERNS: Dict[str, List[str]] = {
    "outward_taxable_supplies": [
        r"outward\s*taxable\s*supplies",
        r"3\.1.*outward\s*taxable",
        r"details\s*of\s*outward\s*supplies",
    ],
    "itc_available": [
        r"itc\s*available",
        r"input\s*tax\s*credit\s*(?:available|availed)",
        r"eligible\s*itc",
    ],
    "tax_paid": [
        r"(?:total\s*)?tax\s*(?:paid|payable)\s*(?:under\s*gst)?",
        r"payment\s*of\s*tax",
        r"gst\s*(?:paid|payable)",
    ],
    "gst_turnover": [
        r"aggregate\s*turnover",
        r"turnover\s*(?:as\s*per|declared\s*in)\s*gst",
        r"annual\s*aggregate\s*turnover",
    ],
    "igst": [r"igst", r"integrated\s*(?:goods\s*(?:and|&)\s*services?\s*)?tax"],
    "cgst": [r"cgst", r"central\s*(?:goods\s*(?:and|&)\s*services?\s*)?tax"],
    "sgst": [r"sgst", r"state\s*(?:goods\s*(?:and|&)\s*services?\s*)?tax"],
}

# Financial year patterns commonly found in Indian statements
_FY_PATTERNS = [
    r"(?:FY|F\.Y\.?)\s*'?20(\d{2})",
    r"(?:for\s*the\s*year\s*ended)\s*(?:31st?\s*)?(?:March|Mar)\s*[,]?\s*20(\d{2})",
    r"20(\d{2})[\s-]*2?0?(\d{2})",
    r"(?:31[\s-]*(?:March|Mar)[\s-]*)20(\d{2})",
    r"(?:As\s*(?:at|on)\s*)(?:31st?\s*)?(?:March|Mar)\s*[,]?\s*20(\d{2})",
    r"(?:Year\s*ended)\s*(?:31st?\s*)?(?:March|Mar)\s*[,]?\s*20(\d{2})",
]

# Consolidated vs Standalone detection
_CONSOLIDATED_RE = re.compile(
    r"consolidated\s*(?:financial|balance|statement|profit|cash)",
    re.IGNORECASE,
)
_STANDALONE_RE = re.compile(
    r"standalone\s*(?:financial|balance|statement|profit|cash)",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════
# Amount parsing (Indian format)
# ═══════════════════════════════════════════════════════════════════════════

_STRIP_RE = re.compile(r"[₹$,\s\u00a0]")  # includes non-breaking space


def _parse_amount(raw: str) -> Optional[float]:
    """Parse Indian-format number: 1,23,456.78 / (negative) / ₹ prefix."""
    if not raw:
        return None
    cleaned = _STRIP_RE.sub("", str(raw)).strip()
    if not cleaned or cleaned in {"-", "–", "—", "NA", "N/A", "nil", "Nil"}:
        return None

    neg = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        neg = True
        cleaned = cleaned[1:-1]
    elif cleaned.startswith("-") or cleaned.startswith("−"):
        neg = True
        cleaned = cleaned[1:]

    # Handle "in crores" / "in lakhs" annotation nearby (caller responsibility)
    try:
        val = float(cleaned)
        return -val if neg else val
    except (ValueError, TypeError):
        return None


def _detect_scale(text: str) -> float:
    """Detect ₹ in Crores / Lakhs / Thousands annotations."""
    t = text[:3000].lower()
    if re.search(r"(?:₹|rs|inr)?\s*(?:in\s*)?crores?", t):
        return 1e7  # 1 crore = 10M
    if re.search(r"(?:₹|rs|inr)?\s*(?:in\s*)?lakhs?", t):
        return 1e5  # 1 lakh = 100K
    if re.search(r"(?:₹|rs|inr)?\s*(?:in\s*)?thousands?", t):
        return 1e3
    return 1.0  # absolute values


# ═══════════════════════════════════════════════════════════════════════════
# PDF extraction — Docling primary, PyMuPDF fallback
# ═══════════════════════════════════════════════════════════════════════════

def _extract_with_docling(file_path: str) -> Tuple[List[List[List[str]]], str]:
    """
    Primary extractor: Docling (IBM) for structured tables.
    Returns (tables, full_text).
    Tries multiple Docling APIs for maximum compatibility across versions.
    """
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(file_path)
        doc = result.document

        tables = []

        # ── Strategy 1: export_to_dataframes() (Docling >= 2.x) ──
        try:
            if hasattr(doc, "export_to_dataframes"):
                dfs = doc.export_to_dataframes()
                for df in dfs:
                    header = [str(c) for c in df.columns.tolist()]
                    rows = [header]
                    for _, row in df.iterrows():
                        rows.append([str(v).strip() for v in row.values])
                    tables.append(rows)
                if tables:
                    logger.info(f"Docling (dataframes): {len(tables)} tables")
        except Exception:
            pass

        # ── Strategy 2: iterate table objects ──
        if not tables:
            try:
                doc_tables = getattr(doc, "tables", []) or []
                for table_obj in doc_tables:
                    # Try to_dataframe() per table
                    if hasattr(table_obj, "to_dataframe"):
                        try:
                            df = table_obj.to_dataframe()
                            header = [str(c) for c in df.columns.tolist()]
                            rows = [header]
                            for _, row in df.iterrows():
                                rows.append([str(v).strip() for v in row.values])
                            tables.append(rows)
                            continue
                        except Exception:
                            pass

                    # Fallback: iterate table.data -> row -> cell.text
                    if hasattr(table_obj, "data"):
                        rows = []
                        for row in table_obj.data:
                            if hasattr(row, "__iter__"):
                                cells = []
                                for cell in row:
                                    cell_text = getattr(cell, "text", str(cell))
                                    cells.append(str(cell_text).strip())
                                rows.append(cells)
                        if rows:
                            tables.append(rows)

                if tables:
                    logger.info(f"Docling (table objects): {len(tables)} tables")
            except Exception:
                pass

        # ── Extract full text ──
        full_text = ""
        # Prefer markdown export (richer structure)
        for method in ("export_to_markdown", "export_to_text"):
            if hasattr(doc, method):
                try:
                    full_text = getattr(doc, method)()
                    if full_text:
                        break
                except Exception:
                    continue

        # Last resort: concatenate table cells
        if not full_text:
            text_parts = []
            for table in tables:
                for row in table:
                    text_parts.append("  ".join(row))
            full_text = "\n".join(text_parts)

        print(f"[FinancialParser] Docling: {len(tables)} tables extracted")
        return tables, full_text
    except ImportError:
        print("[FinancialParser] Docling unavailable — falling back to PyMuPDF")
        return [], ""
    except (Exception, BaseException) as exc:
        print(f"[FinancialParser] Docling failed: {exc} — falling back to PyMuPDF")
        return [], ""


def _extract_with_pymupdf(file_path: str) -> Tuple[List[str], str]:
    """Fallback extractor: PyMuPDF text extraction."""
    pages: List[str] = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
    except Exception as exc:
        print(f"[FinancialParser] PyMuPDF failed: {exc}")
    return pages, "\n".join(pages)


# ═══════════════════════════════════════════════════════════════════════════
# Value extraction from text
# ═══════════════════════════════════════════════════════════════════════════

def _find_value_near(
    text: str,
    patterns: List[str],
    scale: float = 1.0,
) -> Optional[float]:
    """
    Search text for a keyword pattern and extract the nearest numeric value.
    Looks for numbers appearing after the keyword on the same or next line.
    """
    for pattern in patterns:
        regex = re.compile(
            rf"({pattern})"
            r"[\s:.\-]*"
            r"([\d,₹\s\(\)\-−\.]+)",
            re.IGNORECASE,
        )
        m = regex.search(text)
        if m:
            val = _parse_amount(m.group(2))
            if val is not None:
                return val * scale

    # Second pass: look for the keyword line, then grab numbers from same/next line
    lines = text.split("\n")
    for i, line in enumerate(lines):
        for pattern in patterns:
            match_pos = re.search(pattern, line, re.IGNORECASE)
            if match_pos:
                # Get all numbers after keyword position on same line
                after_keyword = line[match_pos.end():]
                nums = re.findall(r"[\d,]+\.?\d*", after_keyword)
                if nums:
                    val = _parse_amount(nums[0])
                    if val is not None:
                        return val * scale

                # Check next line
                if i + 1 < len(lines):
                    nums = re.findall(r"[\d,]+\.?\d*", lines[i + 1])
                    if nums:
                        val = _parse_amount(nums[0])
                        if val is not None:
                            return val * scale
    return None


def _extract_multi_year_from_table(
    tables: List[List[List[str]]],
    scale: float,
) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Extract multi-year data from Docling tables.
    Many Indian financial PDFs have columns: Line Item | FY24 | FY23 | FY22
    Returns {"FY24": {...}, "FY23": {...}, ...}

    Improvements:
    - Scans first 3 rows for year headers (handles merged header rows)
    - Detects "Particulars" column dynamically (not always column 0)
    - Handles FY written as FY'24, FY 2024, 2023-24, etc.
    """
    years_data: Dict[str, Dict[str, Optional[float]]] = {}

    for table in tables:
        if not table or len(table) < 2:
            continue

        # ── Detect year columns from first 3 rows (merged headers) ──
        year_cols: Dict[int, str] = {}
        label_col: int = 0  # default: first column is the label
        header_end: int = 1

        for row_idx in range(min(3, len(table))):
            row = table[row_idx]
            for col_idx, cell in enumerate(row):
                cell_str = str(cell).strip()

                # Detect "Particulars" / "Description" / "Note" column
                if re.search(r"(?:particulars?|description|note|line\s*item)", cell_str, re.IGNORECASE):
                    label_col = col_idx
                    header_end = max(header_end, row_idx + 1)
                    continue

                for fy_pat in _FY_PATTERNS:
                    m = re.search(fy_pat, cell_str)
                    if m:
                        groups = m.groups()
                        if len(groups) == 2:
                            fy = f"FY{groups[1]}"
                        else:
                            fy = f"FY{groups[0]}"
                        if col_idx not in year_cols:
                            year_cols[col_idx] = fy
                            years_data.setdefault(fy, {})
                        header_end = max(header_end, row_idx + 1)
                        break

        if not year_cols:
            continue

        # ── Parse data rows ──
        all_patterns = {**_PNL_PATTERNS, **_BS_PATTERNS, **_CF_PATTERNS}
        for row in table[header_end:]:
            if not row:
                continue
            label = str(row[label_col]).strip().lower() if label_col < len(row) and row[label_col] else ""
            if not label or len(label) < 2:
                continue

            for field_name, keywords in all_patterns.items():
                matched = False
                for kw in keywords:
                    if re.search(kw, label, re.IGNORECASE):
                        matched = True
                        break
                if matched:
                    for col_idx, fy in year_cols.items():
                        if col_idx < len(row):
                            val = _parse_amount(row[col_idx])
                            if val is not None:
                                years_data[fy][field_name] = val * scale
                    break

    return years_data


# ═══════════════════════════════════════════════════════════════════════════
# Statement-level extraction (text-based fallback)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_pnl(text: str, scale: float) -> Dict[str, Optional[float]]:
    """Extract P&L fields using Indian CA patterns."""
    result = {}
    for field, patterns in _PNL_PATTERNS.items():
        result[field] = _find_value_near(text, patterns, scale)

    # Derive totals if missing
    if result.get("total_revenue") is None:
        rev_ops = result.get("revenue_from_operations") or 0
        other = result.get("other_income") or 0
        if rev_ops:
            result["total_revenue"] = rev_ops + other

    if result.get("ebitda") is None and result.get("profit_before_tax") is not None:
        pbt = result["profit_before_tax"] or 0
        dep = result.get("depreciation") or 0
        fin = result.get("finance_cost") or 0
        result["ebitda"] = pbt + dep + fin

    return result


def _extract_bs(text: str, scale: float) -> Dict[str, Optional[float]]:
    """Extract Balance Sheet fields using Indian CA patterns."""
    result = {}
    for field, patterns in _BS_PATTERNS.items():
        result[field] = _find_value_near(text, patterns, scale)

    # Derive net_worth if missing
    if result.get("net_worth") is None:
        sc = result.get("share_capital") or 0
        rs = result.get("reserves_surplus") or 0
        if sc:
            result["net_worth"] = sc + rs

    # Derive total_debt if missing
    if result.get("total_debt") is None:
        lt = result.get("long_term_borrowings") or 0
        st = result.get("short_term_borrowings") or 0
        if lt or st:
            result["total_debt"] = lt + st

    return result


def _extract_cf(text: str, scale: float) -> Dict[str, Optional[float]]:
    """Extract Cash Flow fields."""
    result = {}
    for field, patterns in _CF_PATTERNS.items():
        result[field] = _find_value_near(text, patterns, scale)
    return result


def _extract_gst_summary(text: str, scale: float) -> Dict[str, Any]:
    """
    Extract GST-related information embedded in financial statement annexures.
    Many Indian financial PDFs contain GST notes, GSTIN, aggregate turnover, etc.
    This is NOT a replacement for gst_parser.py — it's for financial-statement-level GST data.
    """
    gst_info: Dict[str, Any] = {}

    # Extract GSTIN(s)
    gstins = _GSTIN_RE.findall(text)
    valid_gstins = []
    for g in gstins:
        try:
            state_code = int(g[:2])
            if 1 <= state_code <= 37:
                valid_gstins.append(g)
        except (ValueError, IndexError):
            continue
    gst_info["gstins_found"] = list(set(valid_gstins))

    # Extract PAN from first valid GSTIN
    if valid_gstins:
        gst_info["pan_from_gstin"] = valid_gstins[0][2:12]

    # Extract GST-related financial values
    for field, patterns in _GST_PATTERNS.items():
        val = _find_value_near(text, patterns, scale)
        if val is not None:
            gst_info[field] = val

    return gst_info


# ═══════════════════════════════════════════════════════════════════════════
# Financial year detection
# ═══════════════════════════════════════════════════════════════════════════

def _detect_financial_years(text: str) -> List[str]:
    """Detect financial years mentioned in the document."""
    years = set()
    for pat in _FY_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            groups = m.groups()
            if len(groups) == 2:
                years.add(f"FY{groups[1]}")
            else:
                years.add(f"FY{groups[0]}")
    return sorted(years, reverse=True)


def _detect_statement_type(text: str) -> str:
    """Detect if financial statements are Consolidated or Standalone."""
    if _CONSOLIDATED_RE.search(text):
        return "consolidated"
    if _STANDALONE_RE.search(text):
        return "standalone"
    return "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# Ratio computation
# ═══════════════════════════════════════════════════════════════════════════

def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 4)


def _compute_ratios(
    pnl: Dict[str, Optional[float]],
    bs: Dict[str, Optional[float]],
    cf: Dict[str, Optional[float]],
) -> Dict[str, Optional[float]]:
    """Compute 8 financial ratios from extracted data."""
    current_ratio = _safe_div(bs.get("current_assets"), bs.get("current_liabilities"))
    net_worth = bs.get("net_worth")
    debt_to_equity = _safe_div(bs.get("total_debt"), net_worth)

    total_debt = bs.get("total_debt") or 0
    pat = pnl.get("profit_after_tax") or pnl.get("pat") or 0
    cfo = cf.get("cfo") or 0
    finance_cost = pnl.get("finance_cost") or 0

    # DSCR = (PAT + Depreciation + Interest) / (Interest + Principal repayment)
    depreciation = pnl.get("depreciation") or 0
    if finance_cost > 0:
        dscr = round((pat + depreciation + finance_cost) / finance_cost, 4)
    else:
        dscr = None

    interest_coverage = _safe_div(
        (pnl.get("ebitda") or (pnl.get("profit_before_tax") or 0) + finance_cost),
        finance_cost,
    )

    revenue = pnl.get("total_revenue") or pnl.get("revenue_from_operations")
    ebitda = pnl.get("ebitda")

    ebitda_margin = _safe_div(ebitda, revenue)
    roe = _safe_div(pat, net_worth)
    pat_margin = _safe_div(pat, revenue)

    return {
        "current_ratio": current_ratio,
        "debt_to_equity": debt_to_equity,
        "dscr": dscr,
        "interest_coverage": interest_coverage,
        "ebitda_margin": ebitda_margin,
        "roe": roe,
        "pat_margin": pat_margin,
        "revenue_cagr": None,  # Computed in multi-year
    }


# ═══════════════════════════════════════════════════════════════════════════
# Confidence scoring + anomaly flags (enriched)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_confidence(
    pnl: Dict, bs: Dict, cf: Dict, ratios: Dict
) -> Tuple[float, List[Dict[str, str]]]:
    """
    Score extraction confidence (0.0 – 1.0) and flag anomalies.

    Checks:
    - Field completeness (8 key fields)
    - Negative revenue / assets / net worth
    - Balance sheet doesn't balance
    - PAT > Revenue (impossible unless non-operating income dominates)
    - EBITDA margin > 100% (likely extraction error)
    - Suspiciously round numbers (exactly ₹1Cr, ₹10Cr)
    - Unusually high/low ratios
    - Both PBT and PAT missing (critical)
    """
    flags: List[Dict[str, str]] = []

    # Count how many key fields were extracted
    key_fields = {
        "total_revenue": pnl.get("total_revenue") or pnl.get("revenue_from_operations"),
        "pat": pnl.get("profit_after_tax") or pnl.get("pat"),
        "total_assets": bs.get("total_assets"),
        "total_debt": bs.get("total_debt"),
        "net_worth": bs.get("net_worth"),
        "current_assets": bs.get("current_assets"),
        "current_liabilities": bs.get("current_liabilities"),
        "cfo": cf.get("cfo"),
    }
    filled = sum(1 for v in key_fields.values() if v is not None)
    total = len(key_fields)
    base_confidence = filled / max(total, 1)

    # ── Critical: both PBT and PAT missing ──
    pbt = pnl.get("profit_before_tax")
    pat_val = key_fields["pat"]
    if pbt is None and pat_val is None:
        flags.append({
            "field": "profit",
            "issue": "Both PBT and PAT missing — likely failed extraction",
            "severity": "high",
        })
        base_confidence -= 0.15

    # ── Negative revenue ──
    rev = key_fields["total_revenue"]
    if rev is not None and rev < 0:
        flags.append({"field": "total_revenue", "issue": "Negative revenue detected", "severity": "high"})
        base_confidence -= 0.1

    # ── PAT > Revenue (unusual) ──
    if rev is not None and pat_val is not None and rev > 0 and pat_val > rev:
        flags.append({
            "field": "profit_after_tax",
            "issue": f"PAT ({pat_val:,.0f}) exceeds Revenue ({rev:,.0f}) — verify extraction",
            "severity": "medium",
        })
        base_confidence -= 0.05

    # ── Negative total assets ──
    assets = key_fields["total_assets"]
    if assets is not None and assets < 0:
        flags.append({"field": "total_assets", "issue": "Negative total assets", "severity": "high"})
        base_confidence -= 0.1

    # ── Balance sheet doesn't balance ──
    nw = key_fields["net_worth"]
    debt = key_fields["total_debt"]
    if nw is not None and debt is not None and assets is not None:
        if abs((nw + debt) - assets) / max(assets, 1) > 0.3:
            flags.append({
                "field": "balance_sheet",
                "issue": "Balance sheet doesn't balance (Net Worth + Debt ≠ Assets)",
                "severity": "medium",
            })
            base_confidence -= 0.05

    # ── EBITDA margin > 100% ──
    ebitda_margin = ratios.get("ebitda_margin")
    if ebitda_margin is not None and ebitda_margin > 1.0:
        flags.append({
            "field": "ebitda_margin",
            "issue": f"EBITDA margin {ebitda_margin*100:.1f}% > 100% — likely extraction error",
            "severity": "medium",
        })
        base_confidence -= 0.05

    # ── Unusually high current ratio ──
    cr = ratios.get("current_ratio")
    if cr is not None and cr > 50:
        flags.append({"field": "current_ratio", "issue": f"Unusually high current ratio ({cr})", "severity": "medium"})
        base_confidence -= 0.05

    # ── Negative D/E ratio ──
    de = ratios.get("debt_to_equity")
    if de is not None and de < 0:
        flags.append({"field": "debt_to_equity", "issue": "Negative D/E ratio", "severity": "medium"})

    # ── Suspiciously round numbers ──
    _ROUND_THRESHOLDS = [1e7, 1e8, 1e9]  # 1Cr, 10Cr, 100Cr
    for field_name in ("total_revenue", "total_assets"):
        val = key_fields.get(field_name)
        if val is not None and val > 0:
            for threshold in _ROUND_THRESHOLDS:
                if val == threshold:
                    flags.append({
                        "field": field_name,
                        "issue": f"Value is exactly ₹{val/1e7:.0f} Cr — may be placeholder",
                        "severity": "low",
                    })
                    break

    return max(0.0, min(1.0, base_confidence)), flags


# ═══════════════════════════════════════════════════════════════════════════
# Benchmark comparison (dynamic from sector_benchmarks table)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_sector_benchmarks(sector: str) -> Dict[str, Any]:
    """Pull benchmarks from sector_benchmarks Supabase table — zero hardcoding."""
    if not get_supabase or not sector:
        return {}
    try:
        supabase = get_supabase()
        result = supabase.table("sector_benchmarks").select("*").eq(
            "sector", sector
        ).eq("is_active", True).execute()
        if result.data:
            return result.data[0]
    except Exception as exc:
        print(f"[FinancialParser] Failed to fetch benchmarks: {exc}")
    return {}


def _compare_to_benchmarks(
    ratios: Dict[str, Optional[float]], benchmarks: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Compare computed ratios against sector benchmarks."""
    comparisons = []
    mapping = {
        "current_ratio": "current_ratio_benchmark",
        "debt_to_equity": "debt_equity_benchmark",
        "dscr": "dscr_benchmark",
        "interest_coverage": "interest_coverage_benchmark",
        "ebitda_margin": "ebitda_margin_benchmark",
        "roe": "roe_benchmark",
        "pat_margin": "pat_margin_benchmark",
    }
    for ratio_key, bench_key in mapping.items():
        actual = ratios.get(ratio_key)
        benchmark = benchmarks.get(bench_key)
        if actual is not None and benchmark is not None:
            benchmark = float(benchmark)
            diff = actual - benchmark
            # For debt metrics, below benchmark is good
            if ratio_key == "debt_to_equity":
                status = "healthy" if diff <= 0 else "elevated"
            else:
                status = "above" if diff >= 0 else "below"
            comparisons.append({
                "ratio": ratio_key,
                "actual": round(actual, 4),
                "benchmark": round(benchmark, 4),
                "difference": round(diff, 4),
                "status": status,
            })
    return comparisons


# ═══════════════════════════════════════════════════════════════════════════
# Store to Supabase
# ═══════════════════════════════════════════════════════════════════════════

def _store_financials(
    application_id: str,
    financial_year: str,
    pnl: Dict,
    bs: Dict,
    cf: Dict,
    ratios: Dict,
    document_id: Optional[str] = None,
    store_to_db: bool = True,
) -> None:
    """Insert a row into extracted_financials table."""
    if not store_to_db or not get_supabase:
        return

    record = {
        "id": str(uuid.uuid4()),
        "application_id": application_id,
        "financial_year": financial_year,
        "total_revenue": pnl.get("total_revenue") or pnl.get("revenue_from_operations"),
        "cost_of_goods": pnl.get("cost_of_materials"),
        "ebitda": pnl.get("ebitda"),
        "pat": pnl.get("profit_after_tax") or pnl.get("pat"),
        "total_assets": bs.get("total_assets"),
        "total_liabilities": bs.get("total_liabilities"),
        "net_worth": bs.get("net_worth"),
        "total_debt": bs.get("total_debt"),
        "current_assets": bs.get("current_assets"),
        "current_liabilities": bs.get("current_liabilities"),
        "cfo": cf.get("cfo"),
        "current_ratio": ratios.get("current_ratio"),
        "debt_to_equity": ratios.get("debt_to_equity"),
        "dscr": ratios.get("dscr"),
        "interest_coverage": ratios.get("interest_coverage"),
        "ebitda_margin": ratios.get("ebitda_margin"),
        "roe": ratios.get("roe"),
        "pat_margin": ratios.get("pat_margin"),
        "revenue_cagr": ratios.get("revenue_cagr"),
        "raw_balance_sheet": bs,
        "raw_profit_loss": pnl,
        "raw_cash_flow": cf,
        "source_document_id": document_id,
    }
    try:
        supabase = get_supabase()
        supabase.table("extracted_financials").insert(record).execute()
        print(f"[FinancialParser] ✓ Stored financials for {financial_year}")
    except Exception as exc:
        print(f"[FinancialParser] ✗ DB insert failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

async def parse_financial_document(
    file_path: str,
    application_id: str,
    financial_year: str = "auto",
    sector: str = "",
    document_id: Optional[str] = None,
    store_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Parse a financial statement PDF.

    Strategy:
    1. Try Docling for structured table extraction (primary)
    2. Fall back to PyMuPDF text extraction
    3. If tables have multi-year columns, extract all years
    4. Compute 8 financial ratios per year
    5. Confidence score + anomaly flags
    6. Benchmark comparison from sector_benchmarks table
    7. Store in extracted_financials Supabase table
    """
    # ── Extract — Docling primary (94%+ accuracy), PyMuPDF fallback ──
    tables, docling_text = _extract_with_docling(file_path)
    pages, pymupdf_text = _extract_with_pymupdf(file_path)
    full_text = docling_text or pymupdf_text
    scale = _detect_scale(full_text)
    statement_type = _detect_statement_type(full_text)

    # ── Detect FYs ────────────────────────────────────────────
    detected_years = _detect_financial_years(full_text)
    if financial_year != "auto" and financial_year not in detected_years:
        detected_years.insert(0, financial_year)
    if not detected_years:
        detected_years = [financial_year if financial_year != "auto" else "unknown"]

    # ── Multi-year from tables (Docling) ──────────────────────
    years_data: Dict[str, Dict[str, Optional[float]]] = {}
    if tables:
        years_data = _extract_multi_year_from_table(tables, scale)

    # ── Per-year results ──────────────────────────────────────
    all_results: List[Dict[str, Any]] = []
    benchmarks = _fetch_sector_benchmarks(sector)

    for fy in detected_years:
        # Prefer table data if available
        if fy in years_data and years_data[fy]:
            raw = years_data[fy]
            pnl = {k: v for k, v in raw.items() if k in _PNL_PATTERNS}
            bs = {k: v for k, v in raw.items() if k in _BS_PATTERNS}
            cf = {k: v for k, v in raw.items() if k in _CF_PATTERNS}
        else:
            # Text-based extraction (single year)
            pnl = _extract_pnl(full_text, scale)
            bs = _extract_bs(full_text, scale)
            cf = _extract_cf(full_text, scale)

        ratios = _compute_ratios(pnl, bs, cf)
        confidence, anomaly_flags = _compute_confidence(pnl, bs, cf, ratios)
        benchmark_comparison = _compare_to_benchmarks(ratios, benchmarks)

        # Store to DB
        _store_financials(application_id, fy, pnl, bs, cf, ratios, document_id, store_to_db)

        all_results.append({
            "financial_year": fy,
            "statement_type": statement_type,
            "profit_and_loss": pnl,
            "balance_sheet": bs,
            "cash_flow": cf,
            "ratios": ratios,
            "confidence": round(confidence, 3),
            "anomaly_flags": anomaly_flags,
            "benchmark_comparison": benchmark_comparison,
        })

        # For text-based extraction, we can only extract one year reliably
        if fy not in years_data:
            break

    # ── Compute Revenue CAGR across years ─────────────────────
    if len(all_results) >= 2:
        revenues = []
        for r in all_results:
            rev = (r["profit_and_loss"].get("total_revenue")
                   or r["profit_and_loss"].get("revenue_from_operations"))
            if rev and rev > 0:
                revenues.append((r["financial_year"], rev))
        revenues.sort(key=lambda x: x[0])
        if len(revenues) >= 2:
            n = len(revenues) - 1
            cagr = (revenues[-1][1] / revenues[0][1]) ** (1 / n) - 1
            for r in all_results:
                r["ratios"]["revenue_cagr"] = round(cagr, 4)

    # ── Extract GST summary from financial statement ──────────
    gst_summary = _extract_gst_summary(full_text, scale)

    return {
        "application_id": application_id,
        "source": "docling" if tables else "pymupdf",
        "statement_type": statement_type,
        "years_detected": detected_years,
        "years_parsed": len(all_results),
        "results": all_results,
        "pages_in_pdf": len(pages),
        "tables_found": len(tables),
        "scale": "crores" if scale == 1e7 else "lakhs" if scale == 1e5 else "thousands" if scale == 1e3 else "absolute",
        "gst_summary": gst_summary,
    }


async def parse_multi_year_financials(
    file_paths: List[Dict[str, str]],
    application_id: str,
    sector: str = "",
) -> Dict[str, Any]:
    """
    Parse multiple financial PDFs (possibly multi-year each).

    Args:
        file_paths: [{"file_path": ..., "financial_year": ..., "document_id": ...}]
        application_id: loan application ID
        sector: company sector for benchmarks
    """
    all_results: List[Dict[str, Any]] = []

    for entry in file_paths:
        result = await parse_financial_document(
            file_path=entry["file_path"],
            application_id=application_id,
            financial_year=entry.get("financial_year", "auto"),
            sector=sector,
            document_id=entry.get("document_id"),
        )
        for yr in result.get("results", []):
            all_results.append(yr)

    # Deduplicate by FY (keep highest confidence)
    by_fy: Dict[str, Dict] = {}
    for r in all_results:
        fy = r["financial_year"]
        if fy not in by_fy or r["confidence"] > by_fy[fy]["confidence"]:
            by_fy[fy] = r
    deduped = sorted(by_fy.values(), key=lambda x: x["financial_year"])

    # Recompute CAGR across all years
    revenues = []
    for r in deduped:
        rev = (r["profit_and_loss"].get("total_revenue")
               or r["profit_and_loss"].get("revenue_from_operations"))
        if rev and rev > 0:
            revenues.append((r["financial_year"], rev))
    revenues.sort(key=lambda x: x[0])
    if len(revenues) >= 2:
        n = len(revenues) - 1
        cagr = (revenues[-1][1] / revenues[0][1]) ** (1 / n) - 1
        for r in deduped:
            r["ratios"]["revenue_cagr"] = round(cagr, 4)

    return {
        "years_parsed": len(deduped),
        "results": deduped,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Test Utility (self-contained — no DB required)
# ═══════════════════════════════════════════════════════════════════════════

def test_parser(pdf_path: str) -> None:
    """
    Quick test: parse a PDF and print extracted values.
    Runs fully self-contained — no Supabase connection needed.

    Usage:
        python -c "from parsers.financial_parser import test_parser; test_parser('path/to/file.pdf')"
    Or:
        python parsers/financial_parser.py path/to/file.pdf
    """
    import asyncio

    async def _run():
        result = await parse_financial_document(
            file_path=pdf_path,
            application_id="test-000",
            financial_year="auto",
            sector="",
            document_id=None,
            store_to_db=False,  # Skip DB writes in test mode
        )

        print("=" * 70)
        print(f"📄 Financial Parser Test — {pdf_path}")
        print(f"   Source:     {result['source']}")
        print(f"   Type:       {result['statement_type']}")
        print(f"   Scale:      {result['scale']}")
        print(f"   Pages:      {result['pages_in_pdf']}")
        print(f"   Tables:     {result['tables_found']}")
        print(f"   Years:      {result['years_detected']}")
        print("=" * 70)

        for yr in result.get("results", []):
            print(f"\n── {yr['financial_year']} (confidence: {yr['confidence']}) ──")

            print("\n  P&L:")
            for k, v in yr["profit_and_loss"].items():
                if v is not None:
                    print(f"    {k:35s} = {v:>15,.2f}")

            print("\n  Balance Sheet:")
            for k, v in yr["balance_sheet"].items():
                if v is not None:
                    print(f"    {k:35s} = {v:>15,.2f}")

            print("\n  Cash Flow:")
            for k, v in yr["cash_flow"].items():
                if v is not None:
                    print(f"    {k:35s} = {v:>15,.2f}")

            print("\n  Ratios:")
            for k, v in yr["ratios"].items():
                if v is not None:
                    print(f"    {k:35s} = {v:>10.4f}")

            if yr["anomaly_flags"]:
                print("\n  ⚠ Anomaly Flags:")
                for flag in yr["anomaly_flags"]:
                    print(f"    [{flag['severity'].upper()}] {flag['field']}: {flag['issue']}")

            if yr["benchmark_comparison"]:
                print("\n  Benchmarks:")
                for bc in yr["benchmark_comparison"]:
                    print(f"    {bc['ratio']:25s}  actual={bc['actual']:.4f}  bench={bc['benchmark']:.4f}  [{bc['status']}]")

        # ── Print GST summary if found ──
        gst = result.get("gst_summary", {})
        if gst:
            print(f"\n{'─' * 70}")
            print("  GST Summary (from financial statement):")
            if gst.get("gstins_found"):
                print(f"    GSTINs found:        {', '.join(gst['gstins_found'])}")
            if gst.get("pan_from_gstin"):
                print(f"    PAN (from GSTIN):    {gst['pan_from_gstin']}")
            for k in ("outward_taxable_supplies", "itc_available", "tax_paid",
                      "gst_turnover", "igst", "cgst", "sgst"):
                if gst.get(k) is not None:
                    print(f"    {k:25s} = ₹{gst[k]:>15,.2f}")

        print("\n" + "=" * 70)

    asyncio.run(_run())


# Allow direct execution: python parsers/financial_parser.py <pdf_path>
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python parsers/financial_parser.py <path_to_pdf>")
        sys.exit(1)
    test_parser(sys.argv[1])
