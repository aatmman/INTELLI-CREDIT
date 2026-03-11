"""
Miscellaneous Parser — Extract data from other corporate loan documents.

3-Layer Extraction Pipeline:
  Layer 1: Docling (primary) — structured table extraction
  Layer 2: PyMuPDF (fallback) — text-based extraction
  Layer 3: EasyOCR (last resort) — scanned/image-based documents

Document types:
  - Shareholding Pattern → Total shares, shareholder list, promoter flags
  - Board Meeting Minutes → Meeting date, agenda, resolutions, directors present
  - Existing Sanction Letter → Bank, loan type, amount, rate, tenure, outstanding
  - Rating Report → Agency, rating, outlook, date, rated amount, strengths/risks

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
        print(f"[MiscParser] Docling: {len(tables)} tables")
        return tables, full_text
    except ImportError:
        return [], ""
    except (Exception, BaseException) as exc:
        print(f"[MiscParser] Docling failed: {exc}")
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
        print(f"[MiscParser] PyMuPDF failed: {exc}")
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
            img_path = f"/tmp/misc_page_{i}.png"
            pix.save(img_path)
            results = reader.readtext(img_path)
            all_text.append(" ".join([r[1] for r in results]))
        doc.close()
        return "\n".join(all_text)
    except ImportError:
        return ""
    except Exception as exc:
        print(f"[MiscParser] OCR failed: {exc}")
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
# Helpers
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

def _extract_shareholding(text: str) -> Dict[str, Any]:
    """Shareholding Pattern."""
    data: Dict[str, Any] = {"shareholders": [], "flags": []}

    data["total_shares"] = _find_amount(text, [
        r"(?:total\s*(?:number\s*of\s*)?shares|total\s*paid[- ]up\s*(?:share\s*)?capital)",
        r"(?:total\s*(?:issued|equity)\s*(?:shares|capital))",
    ])

    # Extract shareholder rows —
    # Common patterns: Name | Shares | %
    lines = text.split("\n")
    for line in lines:
        # Look for lines with name + number + percentage
        m = re.match(
            r"\s*(.{3,50}?)\s+(\d[\d,]*)\s+(\d{1,3}\.?\d{0,2})\s*%?",
            line,
        )
        if m:
            name = m.group(1).strip()
            # Skip header-like rows
            if re.search(r"(?:name|shareholder|category|particular)", name, re.IGNORECASE):
                continue
            shares = _parse_amount(m.group(2))
            pct = float(m.group(3))
            if name and shares:
                data["shareholders"].append({
                    "name": name,
                    "shares": shares,
                    "percentage_holding": pct,
                })

    # Compute promoter holding
    promoter_pct = 0.0
    public_pct = 0.0
    for sh in data["shareholders"]:
        pct = sh.get("percentage_holding", 0)
        if re.search(r"promoter|director|founder", sh.get("name", ""), re.IGNORECASE):
            promoter_pct += pct
        else:
            public_pct += pct

    # Also try direct extraction
    m = re.search(r"(?:promoter|promoters?)\s*(?:holding|group)?\s*[:\-]?\s*(\d{1,3}\.?\d{0,2})\s*%", text, re.IGNORECASE)
    if m:
        promoter_pct = max(promoter_pct, float(m.group(1)))

    data["promoter_holding_pct"] = promoter_pct
    data["public_float_pct"] = 100.0 - promoter_pct if promoter_pct > 0 else public_pct

    # Flags
    if promoter_pct > 75:
        data["flags"].append({
            "flag": "promoter_concentration",
            "severity": "medium",
            "detail": f"Promoter holding {promoter_pct}% > 75% threshold",
        })
    if data["public_float_pct"] and data["public_float_pct"] < 26:
        data["flags"].append({
            "flag": "low_public_float",
            "severity": "medium",
            "detail": f"Public float {data['public_float_pct']}% < 26% minimum",
        })

    return data


def _extract_board_minutes(text: str) -> Dict[str, Any]:
    """Board Meeting Minutes."""
    data: Dict[str, Any] = {"flags": []}

    data["meeting_date"] = _find_date(text, r"(?:date\s*of\s*(?:the\s*)?(?:meeting|board)|held\s*on)")

    # Agenda items — look for numbered/bulleted items after "Agenda"
    agenda_section = re.search(
        r"(?:agenda|items?\s*for\s*discussion|business\s*transacted)\s*[:\-]?\s*\n((?:.+\n){1,20})",
        text, re.IGNORECASE,
    )
    if agenda_section:
        items = re.findall(r"(?:^|\n)\s*(?:\d+[\.\)]\s*|[•\-\*]\s*|(?:item|resolution)\s*\d*\s*[:\-]?\s*)(.+)",
                           agenda_section.group(1), re.IGNORECASE)
        data["agenda_items"] = [i.strip() for i in items if i.strip()]
    else:
        data["agenda_items"] = []

    # Resolutions
    resolutions = re.findall(
        r"(?:resolved|resolution\s*that|unanimously\s*(?:resolved|approved))\s*[:\-]?\s*(.+?)(?:\n|$|\.(?:\s*\n))",
        text, re.IGNORECASE,
    )
    data["resolutions_passed"] = [r.strip() for r in resolutions]

    # Directors present
    directors_section = re.search(
        r"(?:directors?\s*present|members?\s*present|in\s*attendance)\s*[:\-]?\s*\n?((?:.+\n){1,10})",
        text, re.IGNORECASE,
    )
    directors = []
    if directors_section:
        for line in directors_section.group(1).split("\n"):
            line = line.strip()
            if line and not re.match(r"\d+\.|^$", line):
                # Clean up numbering / bullet
                name = re.sub(r"^\d+[\.\)]\s*|^[•\-\*]\s*|^Mr\.\s*|^Ms\.\s*|^Smt\.\s*|^Shri\s*", "", line).strip()
                if name and len(name) > 2:
                    directors.append(name)
    data["directors_present"] = directors

    # Flag alarming resolutions
    alarming_keywords = [
        (r"(?:new\s*)?borrow(?:ing|ed)|(?:fresh|additional)\s*(?:loan|credit|facility)", "new_borrowing"),
        (r"(?:sale|disposal|transfer)\s*(?:of\s*)?(?:asset|property|land)", "asset_sale"),
        (r"change\s*(?:in|of)\s*(?:business|activity|object)", "business_change"),
    ]
    combined_resolutions = " ".join(data["resolutions_passed"])
    for pattern, flag_name in alarming_keywords:
        if re.search(pattern, combined_resolutions, re.IGNORECASE):
            data["flags"].append({
                "flag": flag_name,
                "severity": "high",
                "detail": f"Resolution related to {flag_name.replace('_', ' ')} detected",
            })

    return data


def _extract_sanction_letter(text: str) -> Dict[str, Any]:
    """Existing sanction letter from another bank."""
    data: Dict[str, Any] = {}

    data["bank_name"] = _find_text(text, [
        r"(?:bank|lender|financial\s*institution)\s*(?:name)?\s*[:\-]?\s*(.+?)(?:\n|$)",
        r"^(.+bank.+?)(?:\n)",
    ])

    data["loan_type"] = _find_text(text, [
        r"(?:type\s*of\s*(?:facility|loan|credit)|facility\s*type|nature\s*of\s*facility)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ])

    data["sanctioned_amount"] = _find_amount(text, [
        r"(?:sanction(?:ed)?\s*(?:amount|limit)|facility\s*amount|(?:total\s*)?limit\s*sanction)",
    ])

    data["sanction_date"] = _find_date(text, r"(?:sanction\s*date|date\s*of\s*sanction)")

    # Interest rate
    rate_m = re.search(
        r"(?:(?:rate\s*of\s*)?interest|ROI)\s*[:\-]?\s*(\d{1,2}\.?\d{0,2})\s*%",
        text, re.IGNORECASE,
    )
    data["interest_rate"] = float(rate_m.group(1)) if rate_m else None

    # Tenure
    tenure_m = re.search(
        r"(?:tenure|repayment\s*period|term)\s*[:\-]?\s*(\d+)\s*(?:months?|years?|yrs?)",
        text, re.IGNORECASE,
    )
    data["tenure"] = tenure_m.group(0).strip() if tenure_m else None

    data["outstanding_balance"] = _find_amount(text, [
        r"(?:outstanding|balance\s*(?:as\s*on|outstanding)|current\s*(?:balance|outstanding))",
    ])

    data["collateral_details"] = _find_text(text, [
        r"(?:collateral|security|charge\s*(?:on|over|details?))\s*[:\-]?\s*(.+?)(?:\n\n|\n(?:[A-Z]))",
    ])

    return data


def _extract_rating_report(text: str) -> Dict[str, Any]:
    """Credit rating report."""
    data: Dict[str, Any] = {}

    data["rating_agency"] = _find_text(text, [
        r"((?:CRISIL|ICRA|CARE|India\s*Ratings|Brickwork|Acuit[eé]|SMERA|Infomerics)[A-Za-z\s]*)",
    ])

    # Rating — e.g. "BBB+", "A-", "CRISIL AA"
    rating_m = re.search(
        r"(?:rating|grade)\s*[:\-]?\s*(?:CRISIL|ICRA|CARE|IND)?\s*([A-D][A-D]?[A-D]?[\+\-]?(?:\s*\((?:CE|SO)\))?)",
        text, re.IGNORECASE,
    )
    data["rating"] = rating_m.group(1).strip() if rating_m else None

    outlook_m = re.search(
        r"(?:outlook|watch)\s*[:\-]?\s*((?:Stable|Positive|Negative|Developing|Credit\s*Watch))",
        text, re.IGNORECASE,
    )
    data["outlook"] = outlook_m.group(1).strip() if outlook_m else None

    data["date"] = _find_date(text, r"(?:date\s*of\s*(?:rating|rationale|report|press\s*release))")

    data["rated_amount"] = _find_amount(text, [
        r"(?:rated?\s*(?:amount|facilities?|instrument))",
        r"(?:amount\s*rated)",
    ])

    # Key strengths
    strengths = re.findall(
        r"(?:strength|positive|key\s*(?:rating\s*)?driver)\s*[:\-\n]?\s*[•\-\*\d\.]*\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE,
    )
    data["key_strengths"] = [s.strip() for s in strengths[:5]]

    # Key risks
    risks = re.findall(
        r"(?:weakness|risk|concern|key\s*(?:rating\s*)?(?:weakness|risk|concern))\s*[:\-\n]?\s*[•\-\*\d\.]*\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE,
    )
    data["key_risks"] = [r.strip() for r in risks[:5]]

    return data


# ═══════════════════════════════════════════════════════════════════════════
# Supabase update for sanction letter → existing_loans_detail
# ═══════════════════════════════════════════════════════════════════════════

def _update_existing_loans(application_id: str, sanction_data: Dict) -> None:
    """Update applications.existing_loans_detail JSONB."""
    if not get_supabase:
        return
    try:
        supabase = get_supabase()
        # Fetch current existing_loans_detail
        result = supabase.table("loan_applications").select(
            "existing_loans_detail"
        ).eq("id", application_id).single().execute()

        current = (result.data or {}).get("existing_loans_detail") or []
        if not isinstance(current, list):
            current = []

        current.append({
            "bank_name": sanction_data.get("bank_name"),
            "loan_type": sanction_data.get("loan_type"),
            "sanctioned_amount": sanction_data.get("sanctioned_amount"),
            "outstanding_balance": sanction_data.get("outstanding_balance"),
            "interest_rate": sanction_data.get("interest_rate"),
            "tenure": sanction_data.get("tenure"),
            "sanction_date": sanction_data.get("sanction_date"),
        })

        supabase.table("loan_applications").update({
            "existing_loans_detail": current,
        }).eq("id", application_id).execute()

        print(f"[MiscParser] ✓ Updated existing_loans_detail ({len(current)} entries)")
    except Exception as exc:
        print(f"[MiscParser] ✗ existing_loans_detail update failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Confidence + storage
# ═══════════════════════════════════════════════════════════════════════════

_REQUIRED = {
    "shareholding_pattern": ["total_shares", "shareholders"],
    "board_meeting_minutes": ["meeting_date", "resolutions_passed"],
    "sanction_letter_existing": ["bank_name", "sanctioned_amount"],
    "rating_report": ["rating_agency", "rating"],
}


def _compute_confidence(data: Dict, doc_type: str) -> Dict[str, float]:
    required = _REQUIRED.get(doc_type, [])
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


def _store_to_supabase(application_id: str, doc_type: str, data: Dict, conf: Dict, doc_id: Optional[str] = None) -> None:
    if not get_supabase:
        return
    try:
        supabase = get_supabase()
        update = {"extracted_data": data, "confidence_scores": conf, "status": "parsed"}
        if doc_id:
            supabase.table("documents").update(update).eq("id", doc_id).execute()
        print(f"[MiscParser] ✓ Stored {doc_type}")
    except Exception as exc:
        print(f"[MiscParser] ✗ DB failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

_EXTRACTORS = {
    "shareholding_pattern": _extract_shareholding,
    "board_meeting_minutes": _extract_board_minutes,
    "sanction_letter_existing": _extract_sanction_letter,
    "rating_report": _extract_rating_report,
}


async def parse_miscellaneous_document(
    file_path: str,
    application_id: str,
    document_type: str,
    document_id: Optional[str] = None,
    store_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Parse a miscellaneous document using 3-layer extraction pipeline.

    Args:
        file_path: Path to PDF
        application_id: Loan application ID
        document_type: One of shareholding_pattern, board_meeting_minutes,
                       sanction_letter_existing, rating_report
    """
    text = _get_text(file_path)

    extractor = _EXTRACTORS.get(document_type)
    if not extractor:
        return {"error": f"Unknown misc doc type: {document_type}", "extracted_data": {}}

    extracted_data = extractor(text)
    confidence_scores = _compute_confidence(extracted_data, document_type)

    if store_to_db:
        _store_to_supabase(application_id, document_type, extracted_data, confidence_scores, doc_id=document_id)

        # Special: update existing_loans_detail for sanction letters
        if document_type == "sanction_letter_existing":
            _update_existing_loans(application_id, extracted_data)

    return {
        "application_id": application_id,
        "document_type": document_type,
        "extracted_data": extracted_data,
        "confidence_scores": confidence_scores,
        "flags": extracted_data.get("flags", []),
    }
