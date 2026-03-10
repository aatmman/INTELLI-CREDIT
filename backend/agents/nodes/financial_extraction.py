"""
Financial Extraction Node — LangGraph node for P&L, BS, CF extraction.

Reads financial documents from the `documents` table, calls
`parse_financial_document()` from `parsers/financial_parser.py`, and stores
results in `extracted_financials` table. Updates CreditApplicationState with
extracted financials, ratios, confidence scores, and anomaly flags.

Handles errors gracefully — if parsing fails for a document, marks it
as failed in the `documents` table and continues with the next one.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_financial_docs(application_id: str) -> List[Dict[str, Any]]:
    """Fetch financial-type documents from documents table."""
    financial_types = (
        "balance_sheet", "profit_loss", "profit_and_loss", "cash_flow",
        "audited_financials", "financial_statement", "annual_report",
        "tax_audit_3cd", "cma_data", "provisional_financials",
    )
    try:
        supabase = get_supabase()
        result = supabase.table("documents").select("*").eq(
            "application_id", application_id
        ).in_("document_type", list(financial_types)).order("created_at").execute()
        return result.data or []
    except Exception as exc:
        print(f"[FinancialExtraction] Failed to fetch docs: {exc}")
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
        print(f"[FinancialExtraction] Status update failed: {exc}")


def _fetch_sector(application_id: str) -> str:
    """Get sector from loan_applications table."""
    try:
        supabase = get_supabase()
        result = supabase.table("loan_applications").select(
            "sector"
        ).eq("id", application_id).single().execute()
        return (result.data or {}).get("sector", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def financial_extraction_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Financial Extraction.

    1. Fetch all financial documents for the application
    2. Call parse_financial_document() for each document
    3. Store results in extracted_financials table (handled by parser)
    4. Update state with balance sheet, P&L, cash flow, ratios
    5. Mark documents as parsed/failed in documents table
    """
    state["current_node"] = "financial_extraction"
    state["progress_percent"] = 20
    state["status_message"] = "Extracting financial statements..."

    errors: list = list(state.get("errors") or [])
    warnings: list = list(state.get("warnings") or [])
    application_id = state.get("application_id", "")

    if not application_id:
        errors.append("[financial_extraction] No application_id in state")
        state["errors"] = errors
        return state

    # ── Fetch financial documents ──
    documents = _fetch_financial_docs(application_id)
    sector = state.get("sector") or _fetch_sector(application_id)

    if not documents:
        warnings.append("[financial_extraction] No financial documents found")
        state["warnings"] = warnings
        state["status_message"] = "No financial documents to extract."
        state["progress_percent"] = 25
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
                "financial_year": doc.get("financial_year", "auto"),
            })

    if not file_entries:
        warnings.append("[financial_extraction] Documents have no file URLs")
        state["warnings"] = warnings
        return state

    # ── Parse each document ──
    from parsers.financial_parser import parse_financial_document

    all_results: List[Dict[str, Any]] = []
    all_ratios: List[Dict[str, Any]] = []
    latest_bs: Dict[str, Any] = {}
    latest_pnl: Dict[str, Any] = {}
    latest_cf: Dict[str, Any] = {}
    latest_confidence: float = 0.0
    all_anomalies: List[Dict[str, Any]] = []

    state["status_message"] = f"Parsing {len(file_entries)} financial document(s)..."

    for entry in file_entries:
        doc_id = entry["document_id"]
        try:
            result = await parse_financial_document(
                file_path=entry["file_path"],
                application_id=application_id,
                financial_year=entry.get("financial_year", "auto"),
                sector=sector,
                document_id=doc_id,
                store_to_db=True,  # Stores to extracted_financials table
            )

            all_results.append(result)

            # Collect ratios
            ratios = result.get("ratios", {})
            if ratios:
                all_ratios.append(ratios)

            # Track latest year's data for state
            bs = result.get("balance_sheet", {})
            pnl = result.get("profit_and_loss", {})
            cf = result.get("cash_flow", {})
            confidence = result.get("confidence", 0.0)
            anomalies = result.get("anomaly_flags", [])

            if bs:
                latest_bs = bs
            if pnl:
                latest_pnl = pnl
            if cf:
                latest_cf = cf
            if confidence:
                latest_confidence = confidence
            if anomalies:
                all_anomalies.extend(anomalies)

            # Mark document as parsed
            _update_document_status(doc_id, "parsed", confidence=confidence)

            fy = result.get("financial_year", "?")
            print(f"[FinancialExtraction] ✓ Parsed {fy} (confidence: {confidence:.2f})")

        except Exception as exc:
            error_msg = f"[financial_extraction] Failed to parse doc {doc_id}: {exc}"
            errors.append(error_msg)
            print(error_msg)
            _update_document_status(doc_id, "extraction_failed", error=str(exc))

    # ── Also try multi-year extraction if multiple docs ──
    if len(file_entries) > 1:
        try:
            from parsers.financial_parser import parse_multi_year_financials
            multi_result = await parse_multi_year_financials(
                file_paths=file_entries,
                application_id=application_id,
                sector=sector,
            )
            multi_results = multi_result.get("results", [])
            if multi_results:
                # Use multi-year results if they have more years
                multi_ratios = [r.get("ratios", {}) for r in multi_results if r.get("ratios")]
                if len(multi_ratios) > len(all_ratios):
                    all_ratios = multi_ratios
                    all_results = multi_results
                    latest = multi_results[-1]
                    latest_bs = latest.get("balance_sheet", latest_bs)
                    latest_pnl = latest.get("profit_and_loss", latest_pnl)
                    latest_cf = latest.get("cash_flow", latest_cf)
                    latest_confidence = latest.get("confidence", latest_confidence)
        except Exception as exc:
            # Non-fatal — we already have individual results
            warnings.append(f"[financial_extraction] Multi-year parsing note: {exc}")

    # ── Update state ──
    state["balance_sheet"] = latest_bs
    state["profit_and_loss"] = latest_pnl
    state["cash_flow"] = latest_cf
    state["financial_ratios"] = all_ratios
    state["financial_anomalies"] = all_anomalies

    # Build extraction_results summary
    state["extraction_results"] = {
        "financial_years_extracted": len(all_results),
        "documents_processed": len(file_entries),
        "overall_confidence": latest_confidence,
        "years": [r.get("financial_year", "?") for r in all_results],
    }

    state["errors"] = errors
    state["warnings"] = warnings
    state["progress_percent"] = 28
    state["status_message"] = (
        f"Financial extraction complete. "
        f"{len(all_results)} year(s) extracted from {len(file_entries)} document(s). "
        f"Confidence: {latest_confidence:.2f}"
    )

    return state
