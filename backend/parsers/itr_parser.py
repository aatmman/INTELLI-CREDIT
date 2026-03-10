"""
ITR Parser — Extract Income Tax Return data from Indian ITR PDFs.

3-Layer Extraction Pipeline:
  Layer 1: Docling (primary) — structured table extraction
  Layer 2: PyMuPDF (fallback) — text-based extraction
  Layer 3: EasyOCR (last resort) — scanned/image-based documents

Document Types:
  - ITR-6 (Company) → AY, Gross Income, Total Income, Tax Paid, Revenue,
                       Net Profit, Depreciation, Total Assets, Filing Date
  - ITR-3/ITR-4 (Promoter) → AY, Name, PAN, Gross Income, Total Income,
                               Tax Paid, Business/Salary/HP Income

Multi-year support: accepts list of file paths for 3-year (company) or 2-year (promoter).
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
    """Layer 1: Docling for structured table extraction."""
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
                        header = [str(c) for c in df.columns.tolist()]
                        rows = [header]
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

        print(f"[ITRParser] Docling: {len(tables)} tables extracted")
        return tables, full_text
    except ImportError:
        print("[ITRParser] Docling unavailable — falling back to PyMuPDF")
        return [], ""
    except (Exception, BaseException) as exc:
        print(f"[ITRParser] Docling failed: {exc} — falling back to PyMuPDF")
        return [], ""


def _extract_with_pymupdf(file_path: str) -> Tuple[List[str], str]:
    """Layer 2: PyMuPDF text extraction."""
    pages: List[str] = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
    except Exception as exc:
        print(f"[ITRParser] PyMuPDF failed: {exc}")
    return pages, "\n".join(pages)


def _extract_with_ocr(file_path: str) -> str:
    """Layer 3: EasyOCR for scanned/image-based documents."""
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        doc = fitz.open(file_path)
        all_text = []
        for page_num in range(len(doc)):
            pix = doc[page_num].get_pixmap(dpi=200)
            img_path = f"/tmp/itr_page_{page_num}.png"
            pix.save(img_path)
            results = reader.readtext(img_path)
            all_text.append(" ".join([r[1] for r in results]))
        doc.close()
        return "\n".join(all_text)
    except ImportError:
        print("[ITRParser] EasyOCR not available")
        return ""
    except Exception as exc:
        print(f"[ITRParser] OCR fallback failed: {exc}")
        return ""


def _get_text(file_path: str) -> str:
    """Run 3-layer pipeline, return best text."""
    _, docling_text = _extract_with_docling(file_path)
    _, pymupdf_text = _extract_with_pymupdf(file_path)
    text = docling_text or pymupdf_text
    if len(text.strip()) < 100:
        ocr_text = _extract_with_ocr(file_path)
        if len(ocr_text) > len(text):
            text = ocr_text
    return text


# ═══════════════════════════════════════════════════════════════════════════
# Regex patterns for Indian ITR documents
# ═══════════════════════════════════════════════════════════════════════════

_PAN_RE = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")
_AY_RE = re.compile(r"(?:assessment\s*year|A\.?Y\.?)\s*[:\-]?\s*(\d{4}[\s\-]*\d{2,4})", re.IGNORECASE)
_AY_ALT_RE = re.compile(r"(\d{4})\s*-\s*(\d{2,4})")

_AMOUNT_RE = re.compile(r"[₹$,\s\u00a0]")


def _parse_amount(raw: str) -> Optional[float]:
    if not raw:
        return None
    cleaned = _AMOUNT_RE.sub("", str(raw)).strip()
    if not cleaned or cleaned in {"-", "–", "—", "NA", "nil", "Nil"}:
        return None
    neg = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        neg = True
        cleaned = cleaned[1:-1]
    elif cleaned.startswith("-"):
        neg = True
        cleaned = cleaned[1:]
    try:
        val = float(cleaned)
        return -val if neg else val
    except (ValueError, TypeError):
        return None


def _find_amount_near(text: str, patterns: List[str]) -> Optional[float]:
    """Find a keyword and extract the nearest numeric value."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            # Look for number after keyword
            after = text[m.end():m.end() + 200]
            nums = re.findall(r"[\d,]+\.?\d*", after)
            for n in nums:
                val = _parse_amount(n)
                if val is not None:
                    return val
    return None


def _detect_assessment_year(text: str) -> Optional[str]:
    """Detect Assessment Year from ITR text."""
    m = _AY_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _AY_ALT_RE.search(text[:2000])
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Company ITR-6 extraction
# ═══════════════════════════════════════════════════════════════════════════

def _extract_itr6(text: str) -> Dict[str, Any]:
    """Extract from company ITR-6."""
    data: Dict[str, Any] = {}

    data["assessment_year"] = _detect_assessment_year(text)

    pan = _PAN_RE.search(text)
    data["pan_number"] = pan.group(1) if pan else None

    data["gross_total_income"] = _find_amount_near(text, [
        r"gross\s*total\s*income",
        r"income\s*before\s*deductions",
    ])

    data["total_income"] = _find_amount_near(text, [
        r"total\s*(?:taxable\s*)?income\s*(?:after\s*deductions)?",
        r"net\s*taxable\s*income",
    ])

    data["tax_paid"] = _find_amount_near(text, [
        r"(?:total\s*)?tax\s*(?:paid|payable|liability)",
        r"tax\s*(?:on\s*total|computed)",
        r"self[- ]assessment\s*tax",
    ])

    # Schedule BP — Business income
    data["gross_receipts"] = _find_amount_near(text, [
        r"(?:gross\s*)?(?:receipts?|revenue)\s*(?:from\s*)?(?:business|operations)",
        r"turnover\s*or\s*gross\s*receipts",
        r"schedule\s*BP.*?(?:gross|total)\s*(?:receipts|revenue)",
    ])

    data["net_profit_from_business"] = _find_amount_near(text, [
        r"net\s*profit\s*(?:from\s*)?(?:business|profession)",
        r"profit\s*(?:and\s*)?(?:loss|before\s*tax)",
        r"income\s*from\s*business",
    ])

    data["depreciation_claimed"] = _find_amount_near(text, [
        r"depreciation\s*(?:claimed|allowable|as\s*per\s*IT)",
        r"total\s*depreciation",
    ])

    data["total_assets"] = _find_amount_near(text, [
        r"total\s*assets",
        r"total\s*(?:of\s*)?balance\s*sheet",
    ])

    # Filing info
    data["return_type"] = "Original"
    if re.search(r"revised\s*return|section\s*139\s*\(5\)", text, re.IGNORECASE):
        data["return_type"] = "Revised"

    # Filing date
    m = re.search(
        r"(?:date\s*of\s*filing|filed\s*on|verification\s*date)\s*[:\-]?\s*"
        r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        text, re.IGNORECASE,
    )
    data["filing_date"] = m.group(1) if m else None

    return data


# ═══════════════════════════════════════════════════════════════════════════
# Promoter ITR-3 / ITR-4 extraction
# ═══════════════════════════════════════════════════════════════════════════

def _extract_itr3_4(text: str) -> Dict[str, Any]:
    """Extract from promoter ITR-3 or ITR-4."""
    data: Dict[str, Any] = {}

    data["assessment_year"] = _detect_assessment_year(text)

    # Name of assessee
    name = re.search(
        r"(?:name\s*(?:of\s*(?:the\s*)?)?(?:assessee|individual))\s*[:\-]?\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE,
    )
    data["name_of_assessee"] = name.group(1).strip() if name else None

    pan = _PAN_RE.search(text)
    data["pan_number"] = pan.group(1) if pan else None

    data["gross_total_income"] = _find_amount_near(text, [
        r"gross\s*total\s*income",
    ])

    data["total_income"] = _find_amount_near(text, [
        r"total\s*(?:taxable\s*)?income",
        r"net\s*taxable\s*income",
    ])

    data["tax_paid"] = _find_amount_near(text, [
        r"(?:total\s*)?tax\s*(?:paid|payable)",
        r"tax\s*(?:on\s*total|computed)",
    ])

    data["income_from_business"] = _find_amount_near(text, [
        r"income\s*(?:from\s*)?(?:business|profession)",
        r"profits?\s*(?:and\s*)?gains?\s*(?:from\s*)?(?:business|profession)",
    ])

    data["income_from_salary"] = _find_amount_near(text, [
        r"income\s*(?:from\s*)?salary",
        r"salary\s*income",
    ])

    data["income_from_house_property"] = _find_amount_near(text, [
        r"income\s*(?:from\s*)?house\s*property",
        r"house\s*property\s*income",
    ])

    return data


# ═══════════════════════════════════════════════════════════════════════════
# Confidence + storage
# ═══════════════════════════════════════════════════════════════════════════

_REQUIRED = {
    "company": ["assessment_year", "total_income", "tax_paid", "gross_receipts"],
    "promoter": ["assessment_year", "pan_number", "total_income", "tax_paid"],
}


def _compute_confidence(data: Dict, itr_type: str) -> Dict[str, float]:
    required = _REQUIRED.get(itr_type, [])
    scores: Dict[str, float] = {}
    for field in required:
        val = data.get(field)
        scores[field] = 1.0 if val is not None else 0.0
    scores["overall"] = sum(scores.values()) / max(len(scores), 1)
    return scores


def _store_to_supabase(
    application_id: str,
    extracted_data: Dict,
    confidence_scores: Dict,
    doc_id: Optional[str] = None,
) -> None:
    if not get_supabase:
        return
    try:
        supabase = get_supabase()
        update = {
            "extracted_data": extracted_data,
            "confidence_scores": confidence_scores,
            "status": "parsed",
        }
        if doc_id:
            supabase.table("documents").update(update).eq("id", doc_id).execute()
        print(f"[ITRParser] ✓ Stored ITR data for {extracted_data.get('assessment_year', '?')}")
    except Exception as exc:
        print(f"[ITRParser] ✗ DB update failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

async def parse_itr_document(
    file_path: str,
    application_id: str,
    itr_type: str = "company",
    document_id: Optional[str] = None,
    store_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Parse a single ITR document.

    Args:
        file_path: Path to PDF
        application_id: Loan application ID
        itr_type: "company" (ITR-6) or "promoter" (ITR-3/ITR-4)
        document_id: Optional document row ID
        store_to_db: Whether to write to Supabase
    """
    text = _get_text(file_path)

    if itr_type == "company":
        extracted_data = _extract_itr6(text)
    else:
        extracted_data = _extract_itr3_4(text)

    extracted_data["itr_type"] = itr_type
    confidence_scores = _compute_confidence(extracted_data, itr_type)

    if store_to_db:
        _store_to_supabase(application_id, extracted_data, confidence_scores, doc_id=document_id)

    return {
        "application_id": application_id,
        "itr_type": itr_type,
        "extracted_data": extracted_data,
        "confidence_scores": confidence_scores,
    }


async def parse_multi_year_itr(
    file_paths: List[Dict[str, str]],
    application_id: str,
    itr_type: str = "company",
    store_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Parse multiple ITR documents for multi-year comparison.

    Args:
        file_paths: [{"file_path": ..., "document_id": ...}, ...]
        application_id: Loan application ID
        itr_type: "company" or "promoter"
        store_to_db: Whether to write to Supabase

    Returns: {"years_parsed": N, "results": [...]}
    """
    results: List[Dict[str, Any]] = []

    for entry in file_paths:
        result = await parse_itr_document(
            file_path=entry["file_path"],
            application_id=application_id,
            itr_type=itr_type,
            document_id=entry.get("document_id"),
            store_to_db=store_to_db,
        )
        results.append(result)

    # Deduplicate by assessment year (keep highest confidence)
    by_ay: Dict[str, Dict] = {}
    for r in results:
        ay = r["extracted_data"].get("assessment_year", "unknown")
        existing = by_ay.get(ay)
        if not existing or r["confidence_scores"]["overall"] > existing["confidence_scores"]["overall"]:
            by_ay[ay] = r

    deduped = sorted(by_ay.values(), key=lambda x: x["extracted_data"].get("assessment_year", ""))

    return {
        "application_id": application_id,
        "itr_type": itr_type,
        "years_parsed": len(deduped),
        "results": deduped,
    }
