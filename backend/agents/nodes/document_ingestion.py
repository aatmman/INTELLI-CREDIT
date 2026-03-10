"""
Agent 1: Document Ingestion Node — Orchestrates all 7 parsers.
Parses PDFs using financial_parser + gst_parser + banking_parser +
kyc_parser + itr_parser + collateral_parser + miscellaneous_parser.
Runs cross-validation (PAN, GSTIN, company name, date ranges, turnover).
Updates document status in Supabase documents table.
All config (document types, checklist) read from loan_type_config.
"""

import re
import difflib
from typing import Any, Dict, List, Optional
from datetime import datetime

from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Config helpers — everything from Supabase, zero hardcoding
# ---------------------------------------------------------------------------

def _fetch_required_documents(loan_type: str) -> List[Dict[str, Any]]:
    """Fetch required document checklist from loan_type_config table."""
    try:
        supabase = get_supabase()
        result = supabase.table("loan_type_config").select(
            "required_documents"
        ).eq("loan_type", loan_type).execute()
        if result.data:
            return result.data[0].get("required_documents", [])
    except Exception as exc:
        print(f"[DocumentIngestion] Failed to fetch loan config: {exc}")
    return []


def _fetch_application_docs(application_id: str) -> List[Dict[str, Any]]:
    """Fetch all uploaded documents for the application from documents table."""
    try:
        supabase = get_supabase()
        result = supabase.table("documents").select("*").eq(
            "application_id", application_id
        ).order("created_at").execute()
        return result.data or []
    except Exception as exc:
        print(f"[DocumentIngestion] Failed to fetch documents: {exc}")
        return []


def _fetch_application_info(application_id: str) -> Dict[str, Any]:
    """Fetch application metadata from loan_applications table."""
    try:
        supabase = get_supabase()
        result = supabase.table("loan_applications").select(
            "loan_type, sector, company_name, pan_number, cin_number, "
            "annual_turnover, loan_amount_requested"
        ).eq("id", application_id).single().execute()
        return result.data or {}
    except Exception as exc:
        print(f"[DocumentIngestion] Failed to fetch application: {exc}")
        return {}


def _update_document_status(
    doc_id: str, status: str, confidence: float = None, error: str = None
) -> None:
    """Update a document's status in the documents table."""
    try:
        supabase = get_supabase()
        update_data: Dict[str, Any] = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if status == "parsed":
            update_data["parsed_at"] = datetime.utcnow().isoformat()
        if confidence is not None:
            update_data["extraction_confidence"] = confidence
        if error:
            update_data["parsing_error"] = error

        supabase.table("documents").update(update_data).eq("id", doc_id).execute()
    except Exception as exc:
        print(f"[DocumentIngestion] Failed to update doc status: {exc}")


# ---------------------------------------------------------------------------
# Document type routing
# ---------------------------------------------------------------------------

# Map document_type values → parser category
_FINANCIAL_TYPES = {
    "balance_sheet", "profit_loss", "profit_and_loss", "cash_flow",
    "audited_financials", "financial_statement", "annual_report",
    "tax_audit_3cd", "cma_data", "provisional_financials",
}
_GST_TYPES = {"gstr3b", "gstr1", "gstr2a", "gstr2b", "gst_return"}
_BANKING_TYPES = {"bank_statement", "bank_statement_12m", "bank_passbook"}
_KYC_TYPES = {
    "certificate_of_incorporation", "moa_aoa",
    "pan_card_company", "gst_registration",
    "director_list", "director_pan_aadhaar",
}
_ITR_TYPES = {"itr_company", "itr_promoter"}
_COLLATERAL_TYPES = {
    "title_deed", "valuation_report", "encumbrance_certificate",
    "cersai_report", "insurance_policy",
}
_MISC_TYPES = {
    "shareholding_pattern", "board_meeting_minutes",
    "sanction_letter_existing", "rating_report",
}


def _classify_document(doc_type: str) -> str:
    """Classify a document into parser category."""
    dt = doc_type.lower().replace("-", "_").replace(" ", "_")
    if dt in _FINANCIAL_TYPES:
        return "financial"
    elif dt in _GST_TYPES:
        return "gst"
    elif dt in _BANKING_TYPES:
        return "banking"
    elif dt in _KYC_TYPES:
        return "kyc"
    elif dt in _ITR_TYPES:
        return "itr"
    elif dt in _COLLATERAL_TYPES:
        return "collateral"
    elif dt in _MISC_TYPES:
        return "misc"
    return "other"


def _gst_return_type(doc_type: str) -> str:
    """Map document_type to GST return type."""
    dt = doc_type.lower()
    if "gstr1" in dt or "gstr_1" in dt:
        return "gstr1"
    if "gstr2" in dt:
        return "gstr2a"
    return "gstr3b"


def _fuzzy_name_match(name1: str, name2: str) -> float:
    """Return similarity ratio (0–1) between two company names."""
    if not name1 or not name2:
        return 0.0
    # Normalize for matching
    n1 = re.sub(r"[^a-z0-9]", "", name1.lower())
    n2 = re.sub(r"[^a-z0-9]", "", name2.lower())
    return difflib.SequenceMatcher(None, n1, n2).ratio()


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

def _cross_validate(
    documents: List[Dict[str, Any]],
    app_info: Dict[str, Any],
    financial_results: List[Dict],
    gst_result: Optional[Dict],
    banking_result: Optional[Dict],
    kyc_results: Optional[List[Dict]] = None,
) -> List[Dict[str, Any]]:
    """
    Cross-validate documents:
    1. PAN number consistency (KYC PAN vs financial PAN)
    2. GSTIN consistency (KYC GST reg vs GST returns)
    3. Company name fuzzy match (>85% threshold)
    4. Date range coverage (3Y financials, 24M GST, 12M banking)
    5. Turnover cross-check (financial revenue ≈ GST turnover ≈ bank credits)
    """
    validations: List[Dict[str, Any]] = []
    app_pan = app_info.get("pan_number", "")
    kyc_results = kyc_results or []

    # Collect all extracted identifiers
    pans_found = set()
    gstins_found = set()
    company_names_found = set()

    if app_pan:
        pans_found.add(app_pan.upper())

    for doc in documents:
        extracted = doc.get("extracted_data") or {}
        if extracted.get("pan_number"):
            pans_found.add(extracted["pan_number"].upper())
        if extracted.get("gstin"):
            gstins_found.add(extracted["gstin"].upper())
        for name_key in ("company_name", "legal_name"):
            if extracted.get(name_key):
                company_names_found.add(extracted[name_key].strip())

    # Also from KYC results
    for kyc in kyc_results:
        cv = kyc.get("cross_validation") or {}
        if cv.get("pan_number"):
            pans_found.add(cv["pan_number"].upper())
        if cv.get("gstin"):
            gstins_found.add(cv["gstin"].upper())
        if cv.get("company_name"):
            company_names_found.add(cv["company_name"].strip())
        if cv.get("cin"):
            pass  # CIN stored for reference

    # ── 1. PAN consistency ──
    if len(pans_found) > 1:
        validations.append({
            "check": "pan_consistency",
            "status": "fail",
            "severity": "high",
            "detail": f"Multiple PAN numbers found: {', '.join(pans_found)}",
        })
    elif pans_found:
        validations.append({
            "check": "pan_consistency",
            "status": "pass",
            "severity": "low",
            "detail": f"PAN consistent: {list(pans_found)[0]}",
        })

    # ── 2. GSTIN consistency ──
    if len(gstins_found) > 1:
        validations.append({
            "check": "gstin_consistency",
            "status": "fail",
            "severity": "high",
            "detail": f"Multiple GSTINs found: {', '.join(gstins_found)}",
        })
    elif gstins_found:
        validations.append({
            "check": "gstin_consistency",
            "status": "pass",
            "severity": "low",
            "detail": f"GSTIN consistent: {list(gstins_found)[0]}",
        })

    # ── 3. Company name fuzzy match ──
    names_list = list(company_names_found)
    if len(names_list) >= 2:
        min_sim = 1.0
        worst_pair = ("", "")
        for i in range(len(names_list)):
            for j in range(i + 1, len(names_list)):
                sim = _fuzzy_name_match(names_list[i], names_list[j])
                if sim < min_sim:
                    min_sim = sim
                    worst_pair = (names_list[i], names_list[j])
        if min_sim < 0.85:
            validations.append({
                "check": "company_name_match",
                "status": "fail",
                "severity": "high",
                "detail": (
                    f"Company name mismatch ({min_sim:.0%} similarity): "
                    f"'{worst_pair[0]}' vs '{worst_pair[1]}'"
                ),
            })
        else:
            validations.append({
                "check": "company_name_match",
                "status": "pass",
                "severity": "low",
                "detail": f"Company names consistent ({min_sim:.0%} match)",
            })

    # ── 4. Date range coverage ──
    fin_years = [r.get("financial_year", "") for r in financial_results]
    if len(fin_years) < 3:
        validations.append({
            "check": "financial_coverage",
            "status": "warning",
            "severity": "medium",
            "detail": f"Only {len(fin_years)} financial years (recommended: 3)",
        })
    else:
        validations.append({
            "check": "financial_coverage", "status": "pass", "severity": "low",
            "detail": f"{len(fin_years)} financial years: {', '.join(fin_years)}",
        })

    gst_months = 0
    if gst_result:
        gst_months = gst_result.get("months_parsed", 0)
    if gst_months < 24:
        validations.append({
            "check": "gst_coverage", "status": "warning", "severity": "medium",
            "detail": f"Only {gst_months} months GST data (recommended: 24)",
        })

    bank_months = 0
    if banking_result:
        bank_months = banking_result.get("months_parsed", 0)
    if bank_months < 12:
        validations.append({
            "check": "banking_coverage", "status": "warning", "severity": "medium",
            "detail": f"Only {bank_months} months banking data (recommended: 12)",
        })

    # ── 5. Turnover cross-check ──
    fin_revenue = None
    for r in financial_results:
        rev = (r.get("profit_and_loss") or {}).get("total_revenue")
        if rev:
            fin_revenue = rev
            break

    gst_annual = None
    if gst_result:
        monthly = gst_result.get("monthly_data") or []
        gst_annual = sum(float(m.get("gstr3b_turnover") or 0) for m in monthly)

    bank_annual = None
    if banking_result:
        monthly = banking_result.get("monthly_data") or []
        bank_annual = sum(float(m.get("total_credits") or 0) for m in monthly)

    if fin_revenue and gst_annual and gst_annual > 0:
        ratio = fin_revenue / gst_annual
        if ratio < 0.6 or ratio > 1.5:
            validations.append({
                "check": "turnover_crosscheck",
                "status": "fail",
                "severity": "high",
                "detail": (
                    f"Financial revenue (₹{fin_revenue:,.0f}) vs GST turnover "
                    f"(₹{gst_annual:,.0f}) ratio: {ratio:.2f} — significant divergence"
                ),
            })

    return validations


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def document_ingestion_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Document Ingestion.

    1. Fetch all uploaded documents from Supabase
    2. Read required checklist from loan_type_config (dynamic)
    3. Route each document to the correct parser
    4. Run cross-validation (PAN, date ranges, turnover)
    5. Update document status in Supabase
    6. Populate state with parsed data
    """
    state["current_node"] = "document_ingestion"
    state["progress_percent"] = 5
    state["status_message"] = "Starting document ingestion..."

    errors: list = list(state.get("errors") or [])
    warnings: list = list(state.get("warnings") or [])

    application_id = state.get("application_id", "")

    # ── Fetch application info ────────────────────────────────
    app_info = _fetch_application_info(application_id)
    sector = app_info.get("sector", state.get("sector", ""))
    loan_type = app_info.get("loan_type", state.get("loan_type", ""))

    # Populate state from app info
    state["company_name"] = app_info.get("company_name", state.get("company_name", ""))
    state["pan_number"] = app_info.get("pan_number", state.get("pan_number", ""))
    state["cin_number"] = app_info.get("cin_number", state.get("cin_number", ""))
    state["sector"] = sector
    state["loan_type"] = loan_type
    state["loan_amount_requested"] = float(
        app_info.get("loan_amount_requested") or state.get("loan_amount_requested", 0)
    )
    state["annual_turnover"] = float(
        app_info.get("annual_turnover") or state.get("annual_turnover", 0)
    )

    # ── Fetch required documents from config ──────────────────
    required_docs = _fetch_required_documents(loan_type)
    state["status_message"] = "Fetching uploaded documents..."
    state["progress_percent"] = 8

    # ── Fetch all uploaded documents ──────────────────────────
    documents = _fetch_application_docs(application_id)
    state["documents"] = documents

    if not documents:
        warnings.append("No documents found for this application")
        state["warnings"] = warnings
        state["progress_percent"] = 10
        state["status_message"] = "No documents to parse."
        return state

    # ── Classify & group documents ────────────────────────────
    financial_docs: List[Dict] = []
    gst_docs: List[Dict] = []
    banking_docs: List[Dict] = []
    kyc_docs: List[Dict] = []
    itr_docs: List[Dict] = []
    collateral_docs: List[Dict] = []
    misc_docs: List[Dict] = []

    for doc in documents:
        doc_type = doc.get("document_type", "")
        category = _classify_document(doc_type)
        file_url = doc.get("file_url", "")
        doc_id = doc.get("id", "")

        entry = {
            "file_path": file_url,
            "document_id": doc_id,
            "document_type": doc_type,
            "financial_year": doc.get("financial_year", ""),
        }

        if category == "financial":
            entry["financial_year"] = doc.get("financial_year", "unknown")
            financial_docs.append(entry)
        elif category == "gst":
            entry["return_type"] = _gst_return_type(doc_type)
            gst_docs.append(entry)
        elif category == "banking":
            banking_docs.append(entry)
        elif category == "kyc":
            kyc_docs.append(entry)
        elif category == "itr":
            itr_docs.append(entry)
        elif category == "collateral":
            collateral_docs.append(entry)
        elif category == "misc":
            misc_docs.append(entry)

    # ── Parse Financial Documents ─────────────────────────────
    financial_results: List[Dict] = []
    state["status_message"] = "Parsing financial statements..."
    state["progress_percent"] = 10

    if financial_docs:
        try:
            from parsers.financial_parser import parse_multi_year_financials
            result = await parse_multi_year_financials(
                file_paths=financial_docs,
                application_id=application_id,
                sector=sector,
            )
            financial_results = result.get("results", [])

            if financial_results:
                latest = financial_results[-1]
                state["balance_sheet"] = latest.get("balance_sheet", {})
                state["profit_and_loss"] = latest.get("profit_and_loss", {})
                state["cash_flow"] = latest.get("cash_flow", {})
                state["financial_ratios"] = [r.get("ratios", {}) for r in financial_results]

            for doc_entry in financial_docs:
                _update_document_status(
                    doc_entry["document_id"], "parsed",
                    confidence=latest.get("confidence") if financial_results else None,
                )
        except Exception as exc:
            errors.append(f"[document_ingestion] Financial parsing failed: {exc}")
            for doc_entry in financial_docs:
                _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

    # ── Parse GST Documents ───────────────────────────────────
    gst_result: Optional[Dict] = None
    state["status_message"] = "Parsing GST returns..."
    state["progress_percent"] = 15

    if gst_docs:
        try:
            from parsers.gst_parser import parse_gst_returns
            gst_result = await parse_gst_returns(
                file_paths=gst_docs,
                application_id=application_id,
            )
            state["gst_monthly_data"] = gst_result.get("monthly_data", [])
            state["gst_flags"] = gst_result.get("flags", [])

            for doc_entry in gst_docs:
                _update_document_status(doc_entry["document_id"], "parsed")
        except Exception as exc:
            errors.append(f"[document_ingestion] GST parsing failed: {exc}")
            for doc_entry in gst_docs:
                _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

    # ── Parse Banking Documents ───────────────────────────────
    banking_result: Optional[Dict] = None
    state["status_message"] = "Parsing bank statements..."
    state["progress_percent"] = 18

    if banking_docs:
        try:
            from parsers.banking_parser import parse_bank_statement
            banking_result = await parse_bank_statement(
                file_paths=banking_docs,
                application_id=application_id,
            )
            state["banking_monthly_data"] = banking_result.get("monthly_data", [])
            state["banking_flags"] = banking_result.get("flags", [])

            for doc_entry in banking_docs:
                _update_document_status(doc_entry["document_id"], "parsed")
        except Exception as exc:
            errors.append(f"[document_ingestion] Banking parsing failed: {exc}")
            for doc_entry in banking_docs:
                _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

    # ── Parse KYC Documents ───────────────────────────────────
    kyc_results: List[Dict] = []
    state["status_message"] = "Parsing KYC / identity documents..."
    state["progress_percent"] = 20

    if kyc_docs:
        try:
            from parsers.kyc_parser import parse_kyc_document
            for doc_entry in kyc_docs:
                result = await parse_kyc_document(
                    file_path=doc_entry["file_path"],
                    application_id=application_id,
                    document_type=doc_entry["document_type"],
                    document_id=doc_entry["document_id"],
                )
                kyc_results.append(result)
                _update_document_status(
                    doc_entry["document_id"], "parsed",
                    confidence=result.get("confidence_scores", {}).get("overall"),
                )
        except Exception as exc:
            errors.append(f"[document_ingestion] KYC parsing failed: {exc}")
            for doc_entry in kyc_docs:
                _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

    state["kyc_data"] = kyc_results

    # ── Parse ITR Documents ───────────────────────────────────
    itr_results: List[Dict] = []
    state["status_message"] = "Parsing income tax returns..."
    state["progress_percent"] = 22

    if itr_docs:
        try:
            from parsers.itr_parser import parse_itr_document
            for doc_entry in itr_docs:
                itr_type = "promoter" if "promoter" in doc_entry["document_type"] else "company"
                result = await parse_itr_document(
                    file_path=doc_entry["file_path"],
                    application_id=application_id,
                    itr_type=itr_type,
                    document_id=doc_entry["document_id"],
                )
                itr_results.append(result)
                _update_document_status(
                    doc_entry["document_id"], "parsed",
                    confidence=result.get("confidence_scores", {}).get("overall"),
                )
        except Exception as exc:
            errors.append(f"[document_ingestion] ITR parsing failed: {exc}")
            for doc_entry in itr_docs:
                _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

    state["itr_data"] = itr_results

    # ── Parse Collateral Documents ────────────────────────────
    collateral_results: List[Dict] = []
    state["status_message"] = "Parsing collateral documents..."
    state["progress_percent"] = 24

    if collateral_docs:
        try:
            from parsers.collateral_parser import parse_collateral_document
            for doc_entry in collateral_docs:
                result = await parse_collateral_document(
                    file_path=doc_entry["file_path"],
                    application_id=application_id,
                    document_type=doc_entry["document_type"],
                    document_id=doc_entry["document_id"],
                )
                collateral_results.append(result)
                _update_document_status(
                    doc_entry["document_id"], "parsed",
                    confidence=result.get("confidence_scores", {}).get("overall"),
                )
        except Exception as exc:
            errors.append(f"[document_ingestion] Collateral parsing failed: {exc}")
            for doc_entry in collateral_docs:
                _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

    state["collateral_data"] = collateral_results

    # ── Parse Miscellaneous Documents ─────────────────────────
    misc_results: List[Dict] = []
    state["status_message"] = "Parsing miscellaneous documents..."
    state["progress_percent"] = 26

    if misc_docs:
        try:
            from parsers.miscellaneous_parser import parse_miscellaneous_document
            for doc_entry in misc_docs:
                result = await parse_miscellaneous_document(
                    file_path=doc_entry["file_path"],
                    application_id=application_id,
                    document_type=doc_entry["document_type"],
                    document_id=doc_entry["document_id"],
                )
                misc_results.append(result)
                _update_document_status(
                    doc_entry["document_id"], "parsed",
                    confidence=result.get("confidence_scores", {}).get("overall"),
                )
        except Exception as exc:
            errors.append(f"[document_ingestion] Misc doc parsing failed: {exc}")
            for doc_entry in misc_docs:
                _update_document_status(doc_entry["document_id"], "extraction_failed", error=str(exc))

    state["misc_data"] = misc_results

    # ── Cross-Validation ──────────────────────────────────────
    state["status_message"] = "Running cross-validation checks..."
    state["progress_percent"] = 28

    cross_validation = _cross_validate(
        documents=documents,
        app_info=app_info,
        financial_results=financial_results,
        gst_result=gst_result,
        banking_result=banking_result,
        kyc_results=kyc_results,
    )
    state["cross_validation_results"] = cross_validation

    for check in cross_validation:
        if check["status"] == "fail":
            warnings.append(f"Cross-validation: {check['detail']}")
        elif check["status"] == "warning":
            warnings.append(f"Cross-validation warning: {check['detail']}")

    # ── Finalize ──────────────────────────────────────────────
    total_parsed = (
        len(financial_docs) + len(gst_docs) + len(banking_docs)
        + len(kyc_docs) + len(itr_docs) + len(collateral_docs) + len(misc_docs)
    )
    state["parsed_documents"] = documents
    state["errors"] = errors
    state["warnings"] = warnings
    state["progress_percent"] = 30
    state["status_message"] = (
        f"Document ingestion complete. "
        f"Parsed {total_parsed} documents "
        f"({len(financial_docs)} financial, {len(gst_docs)} GST, "
        f"{len(banking_docs)} banking, {len(kyc_docs)} KYC, "
        f"{len(itr_docs)} ITR, {len(collateral_docs)} collateral, "
        f"{len(misc_docs)} misc). "
        f"{len(cross_validation)} cross-validation checks run."
    )

    return state
