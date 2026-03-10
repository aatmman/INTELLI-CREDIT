"""
Banking Analysis Node — LangGraph node for 12-month bank statement analysis.

Reads bank statement documents from `documents` table, calls
`parse_bank_statement()` from `parsers/banking_parser.py`, stores results
in `bank_statement_data` table. Updates CreditApplicationState with
monthly banking data, anomaly flags, and behavioral indicators.

Also computes supplementary cross-checks: bank credits vs GST turnover,
window dressing detection, and banking conduct score input.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_banking_docs(application_id: str) -> List[Dict[str, Any]]:
    """Fetch bank statement documents from documents table."""
    banking_types = ("bank_statement", "bank_statement_12m", "bank_passbook")
    try:
        supabase = get_supabase()
        result = supabase.table("documents").select("*").eq(
            "application_id", application_id
        ).in_("document_type", list(banking_types)).order("created_at").execute()
        return result.data or []
    except Exception as exc:
        print(f"[BankingAnalysis] Failed to fetch docs: {exc}")
        return []


def _update_document_status(
    doc_id: str,
    status: str,
    confidence: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    """Update document status in documents table."""
    try:
        supabase = get_supabase()
        update: Dict[str, Any] = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if status == "parsed":
            update["parsed_at"] = datetime.utcnow().isoformat()
        if confidence is not None:
            update["extraction_confidence"] = confidence
        if error:
            update["parsing_error"] = error
        supabase.table("documents").update(update).eq("id", doc_id).execute()
    except Exception as exc:
        print(f"[BankingAnalysis] Status update failed: {exc}")


# ---------------------------------------------------------------------------
# Supplementary analysis
# ---------------------------------------------------------------------------

def _detect_window_dressing(monthly_data: List[Dict[str, Any]]) -> bool:
    """
    Detect window dressing: large credits in the last 5 days of a month
    that are reversed in the first 5 days of the next month.

    Simplified heuristic: if end-of-month balance is >2× the monthly
    average balance for 3+ months, flag as window dressing.
    """
    suspicious_months = 0
    for month in monthly_data:
        avg_balance = float(month.get("average_balance") or 0)
        closing_balance = float(month.get("closing_balance") or 0)
        if avg_balance > 0 and closing_balance > 2.0 * avg_balance:
            suspicious_months += 1
    return suspicious_months >= 3


def _crosscheck_bank_vs_gst(
    banking_data: List[Dict[str, Any]],
    state: CreditApplicationState,
) -> List[Dict[str, Any]]:
    """
    Compare bank credits with GST turnover.
    PRD rule: bank_credit / GST_turnover < 0.6x = +25 pts, >1.8x = +40 pts
    """
    flags: List[Dict[str, Any]] = []

    bank_annual = sum(float(m.get("total_credits") or 0) for m in banking_data)
    if bank_annual <= 0:
        return flags

    gst_annual = 0.0
    gst_data = state.get("gst_monthly_data") or []
    for m in gst_data:
        gst_annual += float(m.get("gstr3b_turnover") or m.get("taxable_turnover") or 0)

    if gst_annual <= 0:
        return flags

    ratio = bank_annual / gst_annual

    if ratio < 0.6:
        flags.append({
            "flag": "bank_credit_vs_gst_low",
            "severity": "high",
            "risk_points": 25,
            "detail": (
                f"Bank credits (₹{bank_annual:,.0f}) are only {ratio:.0%} of "
                f"GST turnover (₹{gst_annual:,.0f}) — cash economy suspected"
            ),
        })
    elif ratio > 1.8:
        flags.append({
            "flag": "bank_credit_vs_gst_high",
            "severity": "high",
            "risk_points": 40,
            "detail": (
                f"Bank credits (₹{bank_annual:,.0f}) are {ratio:.0%} of "
                f"GST turnover (₹{gst_annual:,.0f}) — possible round-tripping"
            ),
        })

    return flags


def _compute_basic_conduct_score(
    monthly_data: List[Dict[str, Any]],
    window_dressing: bool,
) -> float:
    """
    Compute a rough banking conduct score (0–100).
    Final score comes from the ML banking_scorer model, but this
    gives a preliminary read for the state pipeline.

    Heuristics:
    - Start at 80 (healthy baseline)
    - Deduct for bounce rate, cash withdrawals, window dressing
    """
    score = 80.0

    total_bounces = sum(int(m.get("bounce_count") or 0) for m in monthly_data)
    total_txns = sum(int(m.get("transaction_count") or 0) for m in monthly_data)
    bounce_rate = total_bounces / max(total_txns, 1)

    # Bounces
    if bounce_rate > 0.10:
        score -= 25
    elif bounce_rate > 0.05:
        score -= 15
    elif bounce_rate > 0.02:
        score -= 8

    # Cash withdrawals >30% of total debits
    total_debits = sum(float(m.get("total_debits") or 0) for m in monthly_data)
    total_cash = sum(float(m.get("cash_withdrawals") or 0) for m in monthly_data)
    if total_debits > 0 and total_cash / total_debits > 0.30:
        score -= 15

    # Window dressing
    if window_dressing:
        score -= 10

    # Insufficient months
    if len(monthly_data) < 12:
        score -= 5

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def banking_analysis_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Banking Analysis.

    1. Fetch all bank statement documents for the application
    2. Call parse_bank_statement() for structured extraction
    3. Results stored in bank_statement_data table (handled by parser)
    4. Detect window dressing patterns
    5. Cross-validate: bank credits vs GST turnover
    6. Compute preliminary banking conduct score
    7. Update state with monthly data, flags, conduct score
    """
    state["current_node"] = "banking_analysis"
    state["progress_percent"] = 35
    state["status_message"] = "Analyzing banking data..."

    errors: list = list(state.get("errors") or [])
    warnings: list = list(state.get("warnings") or [])
    application_id = state.get("application_id", "")

    if not application_id:
        errors.append("[banking_analysis] No application_id in state")
        state["errors"] = errors
        return state

    # ── Fetch banking documents ──
    documents = _fetch_banking_docs(application_id)

    if not documents:
        warnings.append("[banking_analysis] No bank statements found")
        state["warnings"] = warnings
        state["status_message"] = "No bank statements to analyze."
        state["progress_percent"] = 40
        return state

    # ── Build file list ──
    file_entries: List[Dict[str, str]] = []
    for doc in documents:
        file_url = doc.get("file_url") or doc.get("storage_path", "")
        if file_url:
            file_entries.append({
                "file_path": file_url,
                "document_id": doc.get("id", ""),
            })

    if not file_entries:
        warnings.append("[banking_analysis] Bank docs have no file URLs")
        state["warnings"] = warnings
        return state

    # ── Parse bank statements ──
    state["status_message"] = f"Parsing {len(file_entries)} bank statement(s)..."

    try:
        from parsers.banking_parser import parse_bank_statement

        banking_result = await parse_bank_statement(
            file_paths=file_entries,
            application_id=application_id,
        )

        monthly_data = banking_result.get("monthly_data", [])
        banking_flags = banking_result.get("flags", [])
        months_parsed = banking_result.get("months_parsed", len(monthly_data))

        # Update state
        state["banking_monthly_data"] = monthly_data
        state["banking_flags"] = banking_flags

        # Mark docs as parsed
        for doc_entry in file_entries:
            _update_document_status(doc_entry["document_id"], "parsed")

        print(
            f"[BankingAnalysis] ✓ {months_parsed} months parsed, "
            f"{len(banking_flags)} flags"
        )

    except Exception as exc:
        error_msg = f"[banking_analysis] Bank statement parsing failed: {exc}"
        errors.append(error_msg)
        print(error_msg)
        for doc_entry in file_entries:
            _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

        state["banking_monthly_data"] = []
        state["banking_flags"] = []
        state["errors"] = errors
        state["progress_percent"] = 40
        state["status_message"] = f"Banking analysis failed: {exc}"
        return state

    # ── Window dressing detection ──
    state["status_message"] = "Checking for window dressing..."
    window_dressing = _detect_window_dressing(monthly_data)
    state["window_dressing_detected"] = window_dressing

    if window_dressing:
        wd_flag = {
            "flag": "window_dressing_detected",
            "severity": "high",
            "detail": "End-of-month balance significantly exceeds average in 3+ months",
        }
        banking_flags.append(wd_flag)
        state["banking_flags"] = banking_flags
        warnings.append(f"Banking: {wd_flag['detail']}")

    # ── Cross-check: bank credits vs GST ──
    crosscheck_flags = _crosscheck_bank_vs_gst(monthly_data, state)
    if crosscheck_flags:
        banking_flags.extend(crosscheck_flags)
        state["banking_flags"] = banking_flags
        for flag in crosscheck_flags:
            warnings.append(f"Banking cross-check: {flag['detail']}")

    # ── Preliminary conduct score ──
    conduct_score = _compute_basic_conduct_score(monthly_data, window_dressing)
    state["banking_conduct_score"] = conduct_score

    # ── Coverage warning ──
    if months_parsed < 12:
        warnings.append(
            f"[banking_analysis] Only {months_parsed} months bank data "
            f"(recommended: 12)"
        )

    state["errors"] = errors
    state["warnings"] = warnings
    state["progress_percent"] = 42
    state["status_message"] = (
        f"Banking analysis complete. "
        f"{months_parsed} months parsed, {len(banking_flags)} flags. "
        f"Conduct score: {conduct_score:.0f}/100."
    )

    return state
