"""
KYC Parser — Extract identity & legal data from Indian KYC documents.

3-Layer Extraction Pipeline:
  Layer 1: Docling (primary) — structured table extraction
  Layer 2: PyMuPDF (fallback) — text-based extraction
  Layer 3: EasyOCR (last resort) — scanned/image-based documents

Document Types:
  - Certificate of Incorporation → CIN, Company Name, DOI, ROC, State
  - MOA/AOA → Company Name, Address, Object Clause, Authorized Capital
  - PAN Card (Company) → PAN, Company Name, DOI
  - GST Registration → GSTIN, Legal Name, Trade Name, Reg Date, Address
  - Director List → List of directors with Name, DIN, Designation
  - Director PAN/Aadhaar → Name, PAN, Aadhaar (masked)

Stores results in Supabase documents table (extracted_data + confidence_scores JSONB).
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
        # Try export_to_dataframes first
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

        # Fallback: iterate table objects
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

        # Extract text
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

        print(f"[KYCParser] Docling: {len(tables)} tables extracted")
        return tables, full_text
    except ImportError:
        print("[KYCParser] Docling unavailable — falling back to PyMuPDF")
        return [], ""
    except (Exception, BaseException) as exc:
        print(f"[KYCParser] Docling failed: {exc} — falling back to PyMuPDF")
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
        print(f"[KYCParser] PyMuPDF failed: {exc}")
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
            img_path = f"/tmp/kyc_page_{page_num}.png"
            pix.save(img_path)
            results = reader.readtext(img_path)
            all_text.append(" ".join([r[1] for r in results]))
        doc.close()
        return "\n".join(all_text)
    except ImportError:
        print("[KYCParser] EasyOCR not available for scanned PDF fallback")
        return ""
    except Exception as exc:
        print(f"[KYCParser] OCR fallback failed: {exc}")
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
# Regex patterns for Indian KYC documents
# ═══════════════════════════════════════════════════════════════════════════

# CIN: L/U + 5-digit NIC + 2-char state + 4-digit year + 3-char type + 6-digit serial
_CIN_RE = re.compile(r"\b([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b")

# PAN: 5 letters + 4 digits + 1 letter
_PAN_RE = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")

# GSTIN: 2-digit state + PAN + entity + Z + check
_GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]Z[A-Z\d])\b")

# DIN: 8-digit number
_DIN_RE = re.compile(r"\b(\d{8})\b")

# Aadhaar: 12 digits (masked pattern: XXXX XXXX 1234)
_AADHAAR_LAST4_RE = re.compile(r"(?:X{4}\s*X{4}\s*|x{4}\s*x{4}\s*|\*{4}\s*\*{4}\s*)(\d{4})")
_AADHAAR_FULL_RE = re.compile(r"\b(\d{4}\s?\d{4}\s?\d{4})\b")

# Date patterns
_DATE_RE = re.compile(
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})|"
    r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*,?\s*\d{4})",
    re.IGNORECASE,
)

# Amount (₹)
_AMOUNT_RE = re.compile(r"[₹$,\s\u00a0]")


def _parse_amount(raw: str) -> Optional[float]:
    if not raw:
        return None
    cleaned = _AMOUNT_RE.sub("", str(raw)).strip()
    if not cleaned or cleaned in {"-", "–", "—", "NA", "nil"}:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _find_value(text: str, patterns: List[str]) -> Optional[str]:
    """Find first match for any of the given patterns."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return None


def _find_date_near(text: str, keyword: str) -> Optional[str]:
    """Find a date near a keyword."""
    m = re.search(rf"{keyword}[^0-9]{{0,50}}(\d{{1,2}}[/\-\.]\d{{1,2}}[/\-\.]\d{{2,4}})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(rf"{keyword}[^0-9]{{0,50}}(\d{{1,2}}\s+[A-Za-z]+\s*,?\s*\d{{4}})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Document-type-specific extractors
# ═══════════════════════════════════════════════════════════════════════════

def _extract_coi(text: str) -> Dict[str, Any]:
    """Certificate of Incorporation."""
    data: Dict[str, Any] = {}

    cin = _CIN_RE.search(text)
    data["cin"] = cin.group(1) if cin else None

    # Company name — usually near "Company Name" or after CIN line
    name = _find_value(text, [
        r"(?:company\s*name|name\s*of\s*(?:the\s*)?company)\s*[:\-]?\s*(.+?)(?:\n|$)",
        r"(?:hereby\s*certif(?:y|ies)\s+that)\s+(.+?)\s+(?:is|has\s+been)",
    ])
    data["company_name"] = name.strip() if name else None

    data["date_of_incorporation"] = _find_date_near(text, r"(?:date\s*of\s*incorporation|incorporated\s*on)")

    roc = _find_value(text, [
        r"(?:ROC|Registrar\s*of\s*Companies)\s*[:\-]?\s*([A-Za-z\s]+?)(?:\n|,|$)",
    ])
    data["roc"] = roc.strip() if roc else None

    state = _find_value(text, [
        r"(?:state|registered\s*(?:at|in))\s*[:\-]?\s*([A-Za-z\s]+?)(?:\n|,|\.|$)",
    ])
    data["state"] = state.strip() if state else None

    return data


def _extract_moa_aoa(text: str) -> Dict[str, Any]:
    """Memorandum & Articles of Association."""
    data: Dict[str, Any] = {}

    name = _find_value(text, [
        r"(?:name\s*of\s*(?:the\s*)?company)\s*[:\-]?\s*(.+?)(?:\n|$)",
        r"^(.+?(?:limited|ltd|private|pvt))",
    ])
    data["company_name"] = name.strip() if name else None

    addr = _find_value(text, [
        r"(?:registered\s*(?:office|address))\s*[:\-]?\s*(.+?)(?:\n\n|\.\s*\n)",
    ])
    data["registered_address"] = addr.strip() if addr else None

    # Object clause — usually "THE OBJECTS FOR WHICH THE COMPANY IS ESTABLISHED"
    obj = _find_value(text, [
        r"(?:objects?\s*(?:of|for)\s*(?:which|the\s*company))[:\-\s]*(.{50,500}?)(?:\n\n|II\.|ARTICLE)",
    ])
    data["object_clause_summary"] = obj.strip()[:500] if obj else None

    cap = _find_value(text, [
        r"(?:authoris[sz]ed\s*(?:share\s*)?capital)\s*[:\-]?\s*(?:₹|Rs\.?|INR)?\s*([\d,.\s]+)",
    ])
    data["authorized_capital"] = _parse_amount(cap) if cap else None

    return data


def _extract_pan_card(text: str) -> Dict[str, Any]:
    """PAN Card — Company."""
    data: Dict[str, Any] = {}
    pan = _PAN_RE.search(text)
    data["pan_number"] = pan.group(1) if pan else None

    name = _find_value(text, [
        r"(?:name|naam)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["company_name"] = name.strip() if name else None
    data["date_of_incorporation"] = _find_date_near(text, r"(?:date\s*of\s*(?:birth|incorporation)|DOB)")

    return data


def _extract_gst_registration(text: str) -> Dict[str, Any]:
    """GST Registration Certificate."""
    data: Dict[str, Any] = {}

    gstin = _GSTIN_RE.search(text)
    data["gstin"] = gstin.group(1) if gstin else None

    data["legal_name"] = (_find_value(text, [
        r"(?:legal\s*name\s*(?:of\s*(?:the\s*)?)?business)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ]) or "").strip() or None

    data["trade_name"] = (_find_value(text, [
        r"(?:trade\s*name)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ]) or "").strip() or None

    data["registration_date"] = _find_date_near(text, r"(?:date\s*of\s*registration|effective\s*date)")

    addr = _find_value(text, [
        r"(?:principal\s*place\s*of\s*business)\s*[:\-]?\s*(.+?)(?:\n\n|\n(?:additional|state))",
    ])
    data["principal_place_of_business"] = addr.strip() if addr else None

    data["constitution_of_business"] = (_find_value(text, [
        r"(?:constitution\s*of\s*business)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ]) or "").strip() or None

    return data


def _extract_director_list(text: str) -> Dict[str, Any]:
    """List of Directors with DIN."""
    data: Dict[str, Any] = {"directors": []}

    # Find DIN numbers and associate with surrounding text
    dins_found = list(_DIN_RE.finditer(text))

    # Try structured extraction: lines with DIN + Name + Designation
    lines = text.split("\n")
    for line in lines:
        din_match = _DIN_RE.search(line)
        if din_match:
            din = din_match.group(1)
            # Remove DIN from line to get name/designation
            rest = _DIN_RE.sub("", line).strip()
            parts = re.split(r"[,|\t]+", rest)
            name = parts[0].strip() if parts else ""
            designation = parts[1].strip() if len(parts) > 1 else ""

            if name and len(name) > 2:
                data["directors"].append({
                    "name": name,
                    "din": din,
                    "designation": designation or "Director",
                })

    # If no directors found from lines, try table pattern
    if not data["directors"]:
        # Look for name-DIN pairs
        for m in re.finditer(
            r"([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s*[\|,\t]+\s*(\d{8})",
            text,
        ):
            data["directors"].append({
                "name": m.group(1).strip(),
                "din": m.group(2),
                "designation": "Director",
            })

    return data


def _extract_director_pan_aadhaar(text: str) -> Dict[str, Any]:
    """Director PAN + Aadhaar (masked)."""
    data: Dict[str, Any] = {}

    pan = _PAN_RE.search(text)
    data["pan_number"] = pan.group(1) if pan else None

    name = _find_value(text, [
        r"(?:name|naam)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])
    data["name"] = name.strip() if name else None

    # Aadhaar last 4 — try masked format first
    aadhaar_masked = _AADHAAR_LAST4_RE.search(text)
    if aadhaar_masked:
        data["aadhaar_last_4"] = aadhaar_masked.group(1)
    else:
        aadhaar_full = _AADHAAR_FULL_RE.search(text)
        if aadhaar_full:
            digits = re.sub(r"\s", "", aadhaar_full.group(1))
            data["aadhaar_last_4"] = digits[-4:]

    return data


# ═══════════════════════════════════════════════════════════════════════════
# Confidence scoring
# ═══════════════════════════════════════════════════════════════════════════

_REQUIRED_FIELDS = {
    "certificate_of_incorporation": ["cin", "company_name", "date_of_incorporation"],
    "moa_aoa": ["company_name", "registered_address"],
    "pan_card_company": ["pan_number", "company_name"],
    "gst_registration": ["gstin", "legal_name", "registration_date"],
    "director_list": ["directors"],
    "director_pan_aadhaar": ["pan_number", "name"],
}


def _compute_confidence(data: Dict, doc_type: str) -> Dict[str, float]:
    """Compute per-field confidence scores."""
    required = _REQUIRED_FIELDS.get(doc_type, [])
    scores: Dict[str, float] = {}
    for field in required:
        val = data.get(field)
        if val is None or val == "" or val == []:
            scores[field] = 0.0
        elif isinstance(val, list) and len(val) > 0:
            scores[field] = 1.0
        else:
            scores[field] = 1.0
    scores["overall"] = sum(scores.values()) / max(len(scores), 1)
    return scores


# ═══════════════════════════════════════════════════════════════════════════
# Supabase storage
# ═══════════════════════════════════════════════════════════════════════════

def _store_to_supabase(
    application_id: str,
    document_type: str,
    extracted_data: Dict,
    confidence_scores: Dict,
    doc_id: Optional[str] = None,
) -> None:
    """Update documents table with extracted_data and confidence_scores."""
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
        else:
            supabase.table("documents").update(update).eq(
                "application_id", application_id
            ).eq("document_type", document_type).execute()
        print(f"[KYCParser] ✓ Stored {document_type} data")
    except Exception as exc:
        print(f"[KYCParser] ✗ DB update failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

_EXTRACTORS = {
    "certificate_of_incorporation": _extract_coi,
    "moa_aoa": _extract_moa_aoa,
    "pan_card_company": _extract_pan_card,
    "gst_registration": _extract_gst_registration,
    "director_list": _extract_director_list,
    "director_pan_aadhaar": _extract_director_pan_aadhaar,
}


async def parse_kyc_document(
    file_path: str,
    application_id: str,
    document_type: str,
    document_id: Optional[str] = None,
    store_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Parse a KYC document using 3-layer extraction pipeline.

    Args:
        file_path: Path to PDF/image
        application_id: Loan application ID
        document_type: One of certificate_of_incorporation, moa_aoa,
                       pan_card_company, gst_registration, director_list,
                       director_pan_aadhaar
        document_id: Optional document row ID
        store_to_db: Whether to write to Supabase

    Returns:
        Dict with extracted_data, confidence_scores, cross_validation fields
    """
    # ── 3-layer text extraction ──
    text = _get_text(file_path)

    # ── Route to document-specific extractor ──
    extractor = _EXTRACTORS.get(document_type)
    if not extractor:
        return {
            "error": f"Unknown KYC document type: {document_type}",
            "extracted_data": {},
            "confidence_scores": {"overall": 0.0},
        }

    extracted_data = extractor(text)
    confidence_scores = _compute_confidence(extracted_data, document_type)

    # ── Build cross-validation output ──
    cross_validation: Dict[str, Optional[str]] = {
        "pan_number": None,
        "company_name": None,
        "gstin": None,
        "cin": None,
    }
    if extracted_data.get("pan_number"):
        cross_validation["pan_number"] = extracted_data["pan_number"]
    if extracted_data.get("company_name"):
        cross_validation["company_name"] = extracted_data["company_name"]
    if extracted_data.get("legal_name"):
        cross_validation["company_name"] = extracted_data["legal_name"]
    if extracted_data.get("gstin"):
        cross_validation["gstin"] = extracted_data["gstin"]
    if extracted_data.get("cin"):
        cross_validation["cin"] = extracted_data["cin"]

    # ── Store to Supabase ──
    if store_to_db:
        _store_to_supabase(
            application_id, document_type, extracted_data,
            confidence_scores, doc_id=document_id,
        )

    return {
        "application_id": application_id,
        "document_type": document_type,
        "extracted_data": extracted_data,
        "confidence_scores": confidence_scores,
        "cross_validation": cross_validation,
        "extraction_source": "docling+pymupdf+easyocr",
    }
