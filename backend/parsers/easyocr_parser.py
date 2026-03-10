"""
EasyOCR Parser — OCR for scanned Indian documents.
Highest F1 on scanned Indian docs per PRD.
"""

from typing import Any, Dict, List, Optional


async def ocr_document(
    file_path: str,
    languages: List[str] = ["en", "hi"],
) -> Dict[str, Any]:
    """
    OCR a scanned document using EasyOCR.
    
    Args:
        file_path: Path to the image or PDF file
        languages: Languages to detect (default: English + Hindi)
    
    Returns:
        Dict with OCR text, confidence, and bounding boxes
    """
    # TODO: Implement with EasyOCR
    # import easyocr
    # reader = easyocr.Reader(languages)
    # results = reader.readtext(file_path)
    
    return {
        "status": "stub",
        "text": "",
        "results": [],
        "confidence": 0.0,
        "languages": languages,
        "message": "EasyOCR parser stub — implement with easyocr.Reader",
    }


async def ocr_and_extract_pan(file_path: str) -> Optional[str]:
    """Extract PAN number from scanned document."""
    return None


async def ocr_and_extract_cin(file_path: str) -> Optional[str]:
    """Extract CIN number from scanned document."""
    return None
