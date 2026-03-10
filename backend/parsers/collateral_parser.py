"""
Collateral Parser — Extract collateral/security data from Indian loan docs.

3-Layer Extraction Pipeline:
  Layer 1: Docling (primary) — structured table extraction
  Layer 2: PyMuPDF (fallback) — text-based extraction
  Layer 3: EasyOCR (last resort) — scanned/image-based documents

Document Types:
  - Title Deed → Property address, survey/plot, owner, area, type, registration
  - Valuation Report → Address, valuer, market value, forced sale value, method
  - Encumbrance Certificate → Property, period, encumbrance found, details
  - CERSAI Report → Asset ID, security type, amount, institution, status
  - Insurance Policy → Policy number, asset, sum insured, dates, premium

Computes: collateral_coverage_ratio, forced_sale_coverage_ratio.
Stores results in Supabase documents table (extracted_data JSONB).
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

try:
    from services.supabase_client import get_supabase
except ImportError:
    get_supabase = None

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 3-Layer Extraction Pipeline
# ═══════════════════════════════════════════════════════════════════════════

def _extract_with_docling(file_path: str) -> Tuple[List[List[List[str]]], str]:
    """Layer 1: Docling."""
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(file_path)
        doc = result.document
        tables = []
        try:
            if hasattr(doc, "export_to_dataframes"):
                for df in doc.export_to_dataframes():
                    header = [str(c) for c in df.columns.tolist()]
                    rows = [header]
                    for _, row in df.iterrows():
                        rows.append([str(v).strip() for v in row.values])
                    tables.append(rows)
        except Exception:
            pass
        if not tables:
            for table_obj in getattr(doc, "tables", []) or []:
                if hasattr(table_obj, "to_dataframe"):
                    try:
                        df = table_obj.to_dataframe()
                        rows = [[str(c) for c in df.columns.tolist()]]
                        for _, row in df.iterrows():
                            rows.append([str(v).strip() for v in row.values])
                        tables.append(rows)
                        continue
                    except Exception:
                        pass
                if hasattr(table_obj, "data"):
                    rows = []
                    for row in table_obj.data:
                        if hasattr(row, "__iter__"):
                            rows.append([str(getattr(c, "text", c)).strip() for c in row])
                    if rows:
                        tables.append(rows)
        full_text = ""
        for method in ("export_to_markdown", "export_to_text"):
            if hasattr(doc, method):
                try:
                    full_text = getattr(doc, method)()
                    if full_text:
                        break
                except Exception:
                    continue
        if not full_text:
            full_text = "\n".join("  ".join(r) for t in tables for r in t)
        print(f"[CollateralParser] Docling: {len(tables)} tables")
        return tables, full_text
    except ImportError:
        return [], ""
    except (Exception, BaseException) as exc:
        print(f"[CollateralParser] Docling failed: {exc}")
        return [], ""


def _extract_with_pymupdf(file_path: str) -> Tuple[List[str], str]:
    """Layer 2: PyMuPDF."""
    pages: List[str] = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
    except Exception as exc:
        print(f"[CollateralParser] PyMuPDF failed: {exc}")
    return pages, "\n".join(pages)


def _extract_with_ocr(file_path: str) -> str:
    """Layer 3: EasyOCR."""
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        doc = fitz.open(file_path)
        all_text = []
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(dpi=200)
            img_path = f"/tmp/collateral_page_{i}.png"
            pix.save(img_path)
            results = reader.readtext(img_path)
            all_text.append(" ".join([r[1] for r in results]))
        doc.close()
        return "\n".join(all_text)
    except ImportError:
        return ""
    except Exception as exc:
        print(f"[CollateralParser] OCR failed: {exc}")
        return ""


def _get_text(file_path: str) -> str:
    _, docling_text = _extract_with_docling(file_path)
    _, pymupdf_text = _extract_with_pymupdf(file_path)
    text = docling_text or pymupdf_text
    if len(text.strip()) < 100:
        ocr_text = _extract_with_ocr(file_path)
        if len(ocr_text) > len(text):
            text = ocr_text
    return text


# ═══════════════════════════════════════════════════════════════════════════
# Amount parsing
# ═══════════════════════════════════════════════════════════════════════════

_STRIP_RE = re.compile(r"[₹$,\s\u00a0]")


def _parse_amount(raw: str) -> Optional[float]:
    if not raw:
        return None
    cleaned = _STRIP_RE.sub("", str(raw)).strip()
    if not cleaned or cleaned in {"-", "–", "—", "NA", "nil"}:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _find_amount(text: str, patterns: List[str]) -> Optional[float]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            after = text[m.end():m.end() + 200]
            nums = re.findall(r"[\d,]+\.?\d*", after)
            for n in nums:
                val = _parse_amount(n)
                if val is not None:
                    return val
    return None


def _find_text(text: str, patterns: List[str]) -> Optional[str]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip() if m.lastindex else m.group(0).strip()
    return None


def _find_date(text: str, keyword: str) -> Optional[str]:
    m = re.search(rf"{keyword}[^0-9]{{0,60}}(\d{{1,2}}[/\-\.]\d{{1,2}}[/\-\.]\d{{2,4}})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(rf"{keyword}[^0-9]{{0,60}}(\d{{1,2}}\s+[A-Za-z]+\s*,?\s*\d{{4}})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Document-type extractors
# ═══════════════════════════════════════════════════════════════════════════

def _extract_title_deed(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["property_address"] = _find_text(text, [
        r"(?:property\s*(?:address|located\s*at|situated))\s*[:\-]?\s*(.+?)(?:\n\n|\n(?:[A-Z]))",
        r"(?:premises\s*(?:at|situated))\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["survey_plot_number"] = _find_text(text, [
        r"(?:survey|plot|khasra|khata)\s*(?:no|number)\.?\s*[:\-]?\s*(.+?)(?:\n|,|$)",
    ])
    data["owner_name"] = _find_text(text, [
        r"(?:owner|vendor|grantor|executant)\s*(?:name)?\s*[:\-]?\s*(.+?)(?:\n|,|$)",
    ])
    data["area"] = _find_text(text, [
        r"(?:area|extent|measurement)\s*[:\-]?\s*([\d,.\s]+(?:sq\.?\s*(?:ft|m|yard|meter)|acre|hectare|gunta|cent|bigha))",
    ])
    data["property_type"] = _find_text(text, [
        r"(?:property\s*type|nature\s*of\s*property)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["date_of_registration"] = _find_date(text, r"(?:date\s*of\s*(?:registration|execution|deed))")
    data["sub_registrar_office"] = _find_text(text, [
        r"(?:sub[- ]registrar|SRO)\s*(?:office)?\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    return data


def _extract_valuation_report(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["property_address"] = _find_text(text, [
        r"(?:property\s*(?:address|location))\s*[:\-]?\s*(.+?)(?:\n\n|\n(?:[A-Z]))",
    ])
    data["valuer_name"] = _find_text(text, [
        r"(?:valuer|appraiser)\s*(?:name)?\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["valuer_registration_number"] = _find_text(text, [
        r"(?:registration\s*(?:no|number)|license|IBBI\s*reg)\s*[:\-]?\s*([A-Z0-9\-/]+)",
    ])
    data["date_of_valuation"] = _find_date(text, r"(?:date\s*of\s*valuation|valuation\s*date|inspected\s*on)")
    data["market_value"] = _find_amount(text, [
        r"(?:market|fair|realisa?ble)\s*value",
        r"(?:estimated|appraised)\s*(?:market\s*)?value",
    ])
    data["forced_sale_value"] = _find_amount(text, [
        r"(?:forced|distress|quick)\s*sale\s*value",
        r"(?:liquidation|reserve)\s*value",
    ])
    data["property_type"] = _find_text(text, [
        r"(?:type\s*of\s*property|property\s*type|nature)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["construction_age"] = _find_text(text, [
        r"(?:age\s*of\s*(?:construction|building|structure)|year\s*of\s*construction)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["valuation_method"] = _find_text(text, [
        r"(?:method\s*(?:of\s*)?valuation|valuation\s*(?:method|approach))\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    return data


def _extract_encumbrance(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["property_details"] = _find_text(text, [
        r"(?:property\s*(?:details|description|document))\s*[:\-]?\s*(.+?)(?:\n\n|\n(?:[A-Z]))",
        r"(?:schedule\s*(?:of\s*)?property)\s*[:\-]?\s*(.+?)(?:\n\n)",
    ])
    data["period_covered"] = _find_text(text, [
        r"(?:period|from)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\s*(?:to|–|-)\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
    ])
    # Encumbrance found?
    if re.search(r"(?:no\s*encumbrance|nil\s*encumbrance|encumbrance\s*free|not\s*found)", text, re.IGNORECASE):
        data["encumbrance_found"] = False
        data["encumbrance_details"] = None
    elif re.search(r"(?:encumbrance\s*(?:found|exists?|registered))", text, re.IGNORECASE):
        data["encumbrance_found"] = True
        details = _find_text(text, [
            r"(?:details?\s*(?:of\s*)?encumbrance)\s*[:\-]?\s*(.+?)(?:\n\n)",
        ])
        data["encumbrance_details"] = details
    else:
        data["encumbrance_found"] = None
        data["encumbrance_details"] = None
    return data


def _extract_cersai(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["asset_id"] = _find_text(text, [
        r"(?:asset\s*(?:id|identification)|registration\s*(?:no|number))\s*[:\-]?\s*([A-Z0-9\-]+)",
    ])
    data["security_interest_type"] = _find_text(text, [
        r"(?:type\s*of\s*(?:security|charge)|security\s*interest\s*type)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["amount_secured"] = _find_amount(text, [
        r"(?:amount\s*(?:secured|of\s*charge))",
    ])
    data["financial_institution"] = _find_text(text, [
        r"(?:secured\s*creditor|financial\s*institution|lender|bank)\s*(?:name)?\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["date_of_filing"] = _find_date(text, r"(?:date\s*of\s*(?:filing|registration|creation))")
    data["status"] = _find_text(text, [
        r"(?:status)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    return data


def _extract_insurance(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["policy_number"] = _find_text(text, [
        r"(?:policy\s*(?:no|number))\s*[:\-]?\s*([A-Z0-9\-/]+)",
    ])
    data["insured_asset"] = _find_text(text, [
        r"(?:(?:insured\s*)?(?:asset|property|subject\s*matter))\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["sum_insured"] = _find_amount(text, [
        r"(?:sum\s*insured|cover\s*amount|insured\s*value)",
    ])
    data["policy_start_date"] = _find_date(text, r"(?:(?:policy\s*)?(?:start|from|commencement)\s*date)")
    data["policy_end_date"] = _find_date(text, r"(?:(?:policy\s*)?(?:end|expiry|to)\s*date)")
    data["insurance_company"] = _find_text(text, [
        r"(?:insurer|insurance\s*company|underwriter)\s*(?:name)?\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["premium_amount"] = _find_amount(text, [
        r"(?:premium\s*(?:amount|payable))",
    ])
    return data


# ═══════════════════════════════════════════════════════════════════════════
# Coverage ratio computation
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_loan_amount(application_id: str) -> Optional[float]:
    """Fetch loan amount from loan_applications table."""
    if not get_supabase:
        return None
    try:
        supabase = get_supabase()
        result = supabase.table("loan_applications").select(
            "loan_amount_requested"
        ).eq("id", application_id).single().execute()
        if result.data:
            return float(result.data.get("loan_amount_requested") or 0)
    except Exception:
        pass
    return None


def _compute_coverage(extracted: Dict, loan_amount: Optional[float]) -> Dict[str, Optional[float]]:
    market_val = extracted.get("market_value")
    fsv = extracted.get("forced_sale_value")
    coverage: Dict[str, Optional[float]] = {
        "collateral_coverage_ratio": None,
        "forced_sale_coverage_ratio": None,
    }
    if loan_amount and loan_amount > 0:
        if market_val:
            coverage["collateral_coverage_ratio"] = round(market_val / loan_amount, 4)
        if fsv:
            coverage["forced_sale_coverage_ratio"] = round(fsv / loan_amount, 4)
    return coverage


# ═══════════════════════════════════════════════════════════════════════════
# Confidence + storage
# ═══════════════════════════════════════════════════════════════════════════

_REQUIRED = {
    "title_deed": ["property_address", "owner_name"],
    "valuation_report": ["market_value", "forced_sale_value"],
    "encumbrance_certificate": ["encumbrance_found"],
    "cersai_report": ["asset_id", "status"],
    "insurance_policy": ["policy_number", "sum_insured"],
}


def _compute_confidence(data: Dict, doc_type: str) -> Dict[str, float]:
    required = _REQUIRED.get(doc_type, [])
    scores: Dict[str, float] = {}
    for field in required:
        val = data.get(field)
        scores[field] = 1.0 if val is not None else 0.0
    scores["overall"] = sum(scores.values()) / max(len(scores), 1)
    return scores


def _store_to_supabase(application_id: str, doc_type: str, data: Dict, conf: Dict, doc_id: Optional[str] = None) -> None:
    if not get_supabase:
        return
    try:
        supabase = get_supabase()
        update = {"extracted_data": data, "confidence_scores": conf, "status": "parsed"}
        if doc_id:
            supabase.table("documents").update(update).eq("id", doc_id).execute()
        print(f"[CollateralParser] ✓ Stored {doc_type}")
    except Exception as exc:
        print(f"[CollateralParser] ✗ DB failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

_EXTRACTORS = {
    "title_deed": _extract_title_deed,
    "valuation_report": _extract_valuation_report,
    "encumbrance_certificate": _extract_encumbrance,
    "cersai_report": _extract_cersai,
    "insurance_policy": _extract_insurance,
}


async def parse_collateral_document(
    file_path: str,
    application_id: str,
    document_type: str,
    document_id: Optional[str] = None,
    store_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Parse a collateral document using 3-layer extraction pipeline.

    Args:
        file_path: Path to PDF
        application_id: Loan application ID
        document_type: One of title_deed, valuation_report, encumbrance_certificate,
                       cersai_report, insurance_policy
    """
    text = _get_text(file_path)

    extractor = _EXTRACTORS.get(document_type)
    if not extractor:
        return {"error": f"Unknown collateral doc type: {document_type}", "extracted_data": {}}

    extracted_data = extractor(text)
    confidence_scores = _compute_confidence(extracted_data, document_type)

    # Compute coverage ratios for valuation reports
    coverage = {}
    if document_type == "valuation_report":
        loan_amount = _fetch_loan_amount(application_id)
        coverage = _compute_coverage(extracted_data, loan_amount)
        extracted_data.update(coverage)

    if store_to_db:
        _store_to_supabase(application_id, document_type, extracted_data, confidence_scores, doc_id=document_id)

    return {
        "application_id": application_id,
        "document_type": document_type,
        "extracted_data": extracted_data,
        "confidence_scores": confidence_scores,
        "coverage_ratios": coverage,
    }
