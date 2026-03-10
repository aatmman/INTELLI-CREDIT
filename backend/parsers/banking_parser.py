"""
Banking Parser — Parse bank statement PDFs into 12-month transaction data.
Detects bounces, cash withdrawals, EMI patterns.
Stores results in bank_statement_data Supabase table.
"""

import re
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import defaultdict

import fitz  # PyMuPDF

from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Number / date helpers
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(r"[₹$,\s]")


def _parse_amount(raw: str) -> Optional[float]:
    """Parse Indian-format currency string to float."""
    if not raw:
        return None
    cleaned = _AMOUNT_RE.sub("", str(raw)).strip()
    neg = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        neg = True
        cleaned = cleaned[1:-1]
    try:
        val = float(cleaned)
        return -val if neg else val
    except (ValueError, TypeError):
        return None


def _extract_month_year(date_str: str) -> Optional[str]:
    """Extract YYYY-MM from common Indian date formats."""
    # DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"\d{1,2}[/-](\d{1,2})[/-](\d{4})", date_str)
    if m:
        return f"{m.group(2)}-{m.group(1).zfill(2)}"
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-\d{2}", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def _extract_pdf_text(file_path: str) -> str:
    """Extract text with layout preservation for tabular bank statements."""
    text_parts: List[str] = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            # Use 'text' mode — for more layout fidelity use 'blocks'
            text_parts.append(page.get_text("text"))
        doc.close()
    except Exception as exc:
        print(f"[BankingParser] PyMuPDF extraction failed: {exc}")
    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# Account info extraction
# ---------------------------------------------------------------------------

def _extract_account_info(text: str) -> Dict[str, Optional[str]]:
    """Extract bank name and account number from header text."""
    bank_name = None
    account_number = None

    # Common Indian bank name patterns
    bank_patterns = [
        r"(State Bank|SBI|HDFC|ICICI|Axis|Kotak|Punjab National|Bank of Baroda"
        r"|Union Bank|Canara Bank|Bank of India|Indian Bank|Central Bank"
        r"|IndusInd|Yes Bank|Federal Bank|IDBI|RBL)",
    ]
    for pat in bank_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            bank_name = m.group(1).strip()
            break

    # Account number
    m = re.search(r"(?:A/?c|Account)\s*(?:No\.?|Number)\s*[:\-]?\s*(\d{9,18})", text, re.IGNORECASE)
    if m:
        account_number = m.group(1)

    return {"bank_name": bank_name, "account_number": account_number}


# ---------------------------------------------------------------------------
# Transaction parsing
# ---------------------------------------------------------------------------

# Bounce indicators in narration
_BOUNCE_KEYWORDS = [
    r"bounce", r"return", r"dishon", r"unpaid", r"ecs\s*return",
    r"nach\s*return", r"insufficient\s*fund", r"chq\s*ret",
]
_BOUNCE_RE = re.compile("|".join(_BOUNCE_KEYWORDS), re.IGNORECASE)

# Cash withdrawal indicators
_CASH_KEYWORDS = [
    r"atm\s*(?:wd|withdrawal|wdl)", r"cash\s*wd", r"cash\s*withdrawal",
    r"self\s*withdrawal", r"cash\s*wdl", r"counter\s*cash",
]
_CASH_RE = re.compile("|".join(_CASH_KEYWORDS), re.IGNORECASE)

# EMI indicators
_EMI_KEYWORDS = [
    r"emi", r"loan\s*repay", r"equated", r"instalment", r"installment",
    r"nach.*loan", r"si.*loan",
]
_EMI_RE = re.compile("|".join(_EMI_KEYWORDS), re.IGNORECASE)


def _parse_transactions(text: str) -> List[Dict[str, Any]]:
    """
    Parse transaction lines from bank statement text.
    Returns list of transactions with date, narration, debit/credit, balance.
    """
    transactions: List[Dict[str, Any]] = []

    # Common format: DD/MM/YYYY  Narration  Debit  Credit  Balance
    # Flexible regex to capture transaction rows
    txn_re = re.compile(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"  # date
        r"\s+(.*?)"                             # narration
        r"\s+([\d,]+\.?\d*)\s+"                 # amount1 (debit or credit)
        r"([\d,]+\.?\d*)"                       # amount2 (balance or other)
    )

    for line in text.split("\n"):
        line = line.strip()
        m = txn_re.match(line)
        if m:
            date_str = m.group(1)
            narration = m.group(2).strip()
            amt1 = _parse_amount(m.group(3))
            amt2 = _parse_amount(m.group(4))

            # Determine debit vs credit from context
            is_debit = any(kw in narration.lower() for kw in [
                "withdrawal", "debit", "transfer to", "payment", "emi", "nach",
            ])
            is_bounce = bool(_BOUNCE_RE.search(narration))
            is_cash = bool(_CASH_RE.search(narration))
            is_emi = bool(_EMI_RE.search(narration))

            transactions.append({
                "date": date_str,
                "month": _extract_month_year(date_str),
                "narration": narration,
                "debit": amt1 if is_debit else 0,
                "credit": 0 if is_debit else amt1,
                "balance": amt2,
                "is_bounce": is_bounce,
                "bounce_amount": amt1 if is_bounce else 0,
                "is_cash_withdrawal": is_cash,
                "cash_amount": amt1 if is_cash else 0,
                "is_emi": is_emi,
                "emi_amount": amt1 if is_emi else 0,
            })

    return transactions


# ---------------------------------------------------------------------------
# Aggregate to monthly
# ---------------------------------------------------------------------------

def _aggregate_monthly(
    transactions: List[Dict[str, Any]],
    account_info: Dict[str, Optional[str]],
) -> List[Dict[str, Any]]:
    """Aggregate transaction data into monthly summaries."""
    monthly: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "total_credits": 0.0,
        "total_debits": 0.0,
        "bounce_count": 0,
        "bounce_amount": 0.0,
        "cash_withdrawals": 0.0,
        "emi_outflows": 0.0,
        "balances": [],
        "txn_count": 0,
    })

    for txn in transactions:
        month = txn.get("month")
        if not month:
            continue

        m = monthly[month]
        m["total_credits"] += float(txn.get("credit") or 0)
        m["total_debits"] += float(txn.get("debit") or 0)
        m["txn_count"] += 1

        if txn.get("is_bounce"):
            m["bounce_count"] += 1
            m["bounce_amount"] += float(txn.get("bounce_amount") or 0)

        if txn.get("is_cash_withdrawal"):
            m["cash_withdrawals"] += float(txn.get("cash_amount") or 0)

        if txn.get("is_emi"):
            m["emi_outflows"] += float(txn.get("emi_amount") or 0)

        balance = txn.get("balance")
        if balance:
            m["balances"].append(float(balance))

    # Build final monthly rows
    results: List[Dict[str, Any]] = []
    for month in sorted(monthly.keys()):
        m = monthly[month]
        balances = m["balances"]
        closing = balances[-1] if balances else 0
        avg_balance = sum(balances) / len(balances) if balances else 0

        results.append({
            "month": month,
            "bank_name": account_info.get("bank_name"),
            "account_number": account_info.get("account_number"),
            "total_credits": round(m["total_credits"], 2),
            "total_debits": round(m["total_debits"], 2),
            "closing_balance": round(closing, 2),
            "average_balance": round(avg_balance, 2),
            "bounce_count": m["bounce_count"],
            "bounce_amount": round(m["bounce_amount"], 2),
            "cash_withdrawals": round(m["cash_withdrawals"], 2),
            "emi_outflows": round(m["emi_outflows"], 2),
        })

    return results


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def _detect_banking_flags(monthly_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect banking red flags from monthly data."""
    flags: List[Dict[str, Any]] = []

    for row in monthly_data:
        month = row["month"]

        # High bounce count
        if row["bounce_count"] >= 3:
            flags.append({
                "month": month, "type": "high_bounces",
                "severity": "high",
                "detail": f"{row['bounce_count']} bounces totalling ₹{row['bounce_amount']:.0f}",
            })

        # High cash withdrawal ratio
        if row["total_credits"] > 0:
            cash_ratio = row["cash_withdrawals"] / row["total_credits"]
            if cash_ratio > 0.5:
                flags.append({
                    "month": month, "type": "high_cash_withdrawal",
                    "severity": "medium",
                    "detail": f"Cash withdrawals {cash_ratio*100:.1f}% of credits",
                })

        # High EMI burden
        if row["total_credits"] > 0:
            emi_ratio = row["emi_outflows"] / row["total_credits"]
            if emi_ratio > 0.6:
                flags.append({
                    "month": month, "type": "high_emi_burden",
                    "severity": "medium",
                    "detail": f"EMI outflows {emi_ratio*100:.1f}% of credits",
                })

    return flags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_bank_statement(
    file_paths: List[Dict[str, str]],
    application_id: str,
) -> Dict[str, Any]:
    """
    Parse bank statement PDFs into 12-month transaction data.

    Args:
        file_paths: list of {"file_path": ..., "document_id": ...}
        application_id: loan application ID

    Returns dict with monthly data, flags, and account info.
    Stores each month's row in bank_statement_data Supabase table.
    """
    all_transactions: List[Dict[str, Any]] = []
    account_info: Dict[str, Optional[str]] = {}

    for entry in file_paths:
        fpath = entry["file_path"]
        text = _extract_pdf_text(fpath)

        # Extract account info from first file
        if not account_info.get("bank_name"):
            account_info = _extract_account_info(text)

        transactions = _parse_transactions(text)
        all_transactions.extend(transactions)

    # Aggregate to monthly
    monthly_data = _aggregate_monthly(all_transactions, account_info)

    # Detect flags
    flags = _detect_banking_flags(monthly_data)

    # Store in Supabase
    try:
        supabase = get_supabase()
        for row in monthly_data:
            record = {
                "id": str(uuid.uuid4()),
                "application_id": application_id,
                "month": row["month"],
                "bank_name": row.get("bank_name"),
                "account_number": row.get("account_number"),
                "total_credits": row.get("total_credits"),
                "total_debits": row.get("total_debits"),
                "closing_balance": row.get("closing_balance"),
                "average_balance": row.get("average_balance"),
                "bounce_count": row.get("bounce_count", 0),
                "bounce_amount": row.get("bounce_amount", 0),
                "cash_withdrawals": row.get("cash_withdrawals", 0),
                "emi_outflows": row.get("emi_outflows", 0),
                "source_document_id": file_paths[0].get("document_id") if file_paths else None,
            }
            supabase.table("bank_statement_data").insert(record).execute()
        print(f"[BankingParser] ✓ Stored {len(monthly_data)} months of banking data")
    except Exception as exc:
        print(f"[BankingParser] ✗ DB insert failed: {exc}")

    return {
        "application_id": application_id,
        "account_info": account_info,
        "months_parsed": len(monthly_data),
        "monthly_data": monthly_data,
        "total_transactions": len(all_transactions),
        "flags": flags,
        "total_flags": len(flags),
        "total_bounces": sum(r["bounce_count"] for r in monthly_data),
    }
