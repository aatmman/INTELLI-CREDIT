"""
GST Analysis Node — LangGraph node for 24-month GST processing.

Reads GST return documents from `documents` table, calls
`parse_gst_returns()` from `parsers/gst_parser.py`, stores results in
`gst_monthly_data` table. Updates CreditApplicationState with monthly
GST data, anomaly flags, and circular trading indicators.

Also runs cross-validation between GST turnover and financial revenue
when financial data is already available in state.
"""

import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_gst_docs(application_id: str) -> List[Dict[str, Any]]:
    """Fetch GST-type documents from documents table."""
    gst_types = ("gstr3b", "gstr1", "gstr2a", "gstr2b", "gst_return")
    try:
        supabase = get_supabase()
        result = supabase.table("documents").select("*").eq(
            "application_id", application_id
        ).in_("document_type", list(gst_types)).order("created_at").execute()
        return result.data or []
    except Exception as exc:
        print(f"[GSTAnalysis] Failed to fetch docs: {exc}")
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
        print(f"[GSTAnalysis] Status update failed: {exc}")


def _detect_return_type(doc_type: str) -> str:
    """Map document_type to GST return type."""
    dt = doc_type.lower()
    if "gstr1" in dt or "gstr_1" in dt:
        return "gstr1"
    if "gstr2" in dt:
        return "gstr2a"
    return "gstr3b"


# ---------------------------------------------------------------------------
# GST vs Financial cross-check
# ---------------------------------------------------------------------------

def _crosscheck_gst_vs_financial(
    gst_data: List[Dict[str, Any]],
    state: CreditApplicationState,
) -> List[Dict[str, Any]]:
    """
    Compare GST annual turnover with financial statement revenue.
    Returns flags if significant divergence found.
    """
    flags: List[Dict[str, Any]] = []

    # Sum up 12 months of GST turnover (latest year)
    gst_annual = 0.0
    for month in gst_data:
        gst_annual += float(month.get("gstr3b_turnover") or month.get("taxable_turnover") or 0)

    if gst_annual <= 0:
        return flags

    # Get financial revenue from state
    pnl = state.get("profit_and_loss") or {}
    fin_revenue = pnl.get("total_revenue") or pnl.get("revenue_from_operations")
    if not fin_revenue:
        return flags

    ratio = float(fin_revenue) / gst_annual if gst_annual > 0 else 0
    state["gst_vs_financial_ratio"] = round(ratio, 4)

    if ratio < 0.6:
        flags.append({
            "flag": "gst_financial_divergence_low",
            "severity": "high",
            "detail": (
                f"Financial revenue (₹{fin_revenue:,.0f}) is only {ratio:.0%} of "
                f"GST turnover (₹{gst_annual:,.0f}) — possible under-reporting"
            ),
        })
    elif ratio > 1.8:
        flags.append({
            "flag": "gst_financial_divergence_high",
            "severity": "high",
            "detail": (
                f"Financial revenue (₹{fin_revenue:,.0f}) is {ratio:.0%} of "
                f"GST turnover (₹{gst_annual:,.0f}) — GST under-filing suspected"
            ),
        })

    return flags


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def gst_analysis_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — GST Analysis.

    1. Fetch all GST documents for the application
    2. Call parse_gst_returns() for structured extraction
    3. Results stored in gst_monthly_data table (handled by parser)
    4. Run cross-validation: GST turnover vs Financial revenue
    5. Update state with monthly data, flags, circular trading score
    """
    state["current_node"] = "gst_analysis"
    state["progress_percent"] = 30
    state["status_message"] = "Analyzing GST data..."

    errors: list = list(state.get("errors") or [])
    warnings: list = list(state.get("warnings") or [])
    application_id = state.get("application_id", "")

    if not application_id:
        errors.append("[gst_analysis] No application_id in state")
        state["errors"] = errors
        return state

    # ── Fetch GST documents ──
    documents = _fetch_gst_docs(application_id)

    if not documents:
        warnings.append("[gst_analysis] No GST documents found")
        state["warnings"] = warnings
        state["status_message"] = "No GST documents to analyze."
        state["progress_percent"] = 35
        return state

    # ── Build file list for parser ──
    file_entries: List[Dict[str, str]] = []
    for doc in documents:
        file_url = doc.get("file_url") or doc.get("storage_path", "")
        if file_url:
            file_entries.append({
                "file_path": file_url,
                "document_id": doc.get("id", ""),
                "document_type": doc.get("document_type", ""),
                "return_type": _detect_return_type(doc.get("document_type", "")),
            })

    if not file_entries:
        warnings.append("[gst_analysis] GST documents have no file URLs")
        state["warnings"] = warnings
        return state

    # ── Parse GST returns ──
    state["status_message"] = f"Parsing {len(file_entries)} GST document(s)..."

    try:
        from parsers.gst_parser import parse_gst_returns

        gst_result = await parse_gst_returns(
            file_paths=file_entries,
            application_id=application_id,
        )

        monthly_data = gst_result.get("monthly_data", [])
        gst_flags = gst_result.get("flags", [])
        months_parsed = gst_result.get("months_parsed", len(monthly_data))

        # Update state
        state["gst_monthly_data"] = monthly_data
        state["gst_flags"] = gst_flags

        # Extract circular trading score if available
        ct_score = gst_result.get("circular_trading_score", 0.0)
        ct_flags = gst_result.get("circular_trading_flags", [])
        state["circular_trading_score"] = ct_score
        state["circular_trading_flags"] = ct_flags

        # Mark all GST docs as parsed
        for doc_entry in file_entries:
            _update_document_status(doc_entry["document_id"], "parsed")

        print(
            f"[GSTAnalysis] ✓ {months_parsed} months parsed, "
            f"{len(gst_flags)} flags, CT score: {ct_score}"
        )

    except Exception as exc:
        error_msg = f"[gst_analysis] GST parsing failed: {exc}"
        errors.append(error_msg)
        print(error_msg)
        for doc_entry in file_entries:
            _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

        state["gst_monthly_data"] = []
        state["gst_flags"] = []
        state["errors"] = errors
        state["progress_percent"] = 35
        state["status_message"] = f"GST analysis failed: {exc}"
        return state

    # ── Cross-validate GST vs Financial ──
    state["status_message"] = "Cross-validating GST vs financial data..."
    crosscheck_flags = _crosscheck_gst_vs_financial(monthly_data, state)
    if crosscheck_flags:
        gst_flags.extend(crosscheck_flags)
        state["gst_flags"] = gst_flags
        for flag in crosscheck_flags:
            warnings.append(f"GST cross-check: {flag['detail']}")

    # ── Warn if insufficient coverage ──
    months_parsed = len(monthly_data)
    if months_parsed < 24:
        warnings.append(
            f"[gst_analysis] Only {months_parsed} months GST data "
            f"(recommended: 24)"
        )

    state["errors"] = errors
    state["warnings"] = warnings
    state["progress_percent"] = 38
    state["status_message"] = (
        f"GST analysis complete. "
        f"{months_parsed} months parsed, {len(gst_flags)} flags raised."
    )

    return state
