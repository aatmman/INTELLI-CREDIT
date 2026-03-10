"""
Document management Pydantic schemas.
Stage 1 — Smart document upload + parsing status.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from schemas.common import DocumentStatus, LoanType


class DocumentUploadRequest(BaseModel):
    """Metadata sent along with file upload."""
    application_id: str
    document_type: str = Field(..., description="Type of document (e.g., 'itr', 'gst_return', 'bank_statement', 'balance_sheet')")
    financial_year: Optional[str] = Field(None, description="Financial year (e.g., 'FY2024')")
    description: Optional[str] = None


class DocumentRecord(BaseModel):
    """Document record from database."""
    id: str
    application_id: str
    document_type: str
    file_name: str
    file_url: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    status: DocumentStatus = DocumentStatus.UPLOADED
    financial_year: Optional[str] = None
    extraction_confidence: Optional[float] = None
    extracted_data: Optional[Dict[str, Any]] = None
    parsing_error: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    parsed_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None


class DocumentChecklist(BaseModel):
    """Document type checklist for a specific loan type."""
    loan_type: LoanType
    required_documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {type, label, required, category} objects"
    )


class DocumentVerificationRequest(BaseModel):
    """RM document verification action."""
    document_id: str
    action: str = Field(..., description="verify | reject | request_reupload")
    remarks: Optional[str] = None


class DocumentCompletenessResponse(BaseModel):
    """Document upload completeness status."""
    application_id: str
    loan_type: LoanType
    total_required: int
    total_uploaded: int
    total_parsed: int
    total_verified: int
    completeness_percent: float
    missing_documents: List[str] = Field(default_factory=list)
    documents: List[DocumentRecord] = Field(default_factory=list)


class CrossValidationResult(BaseModel):
    """AI cross-document validation result."""
    check_name: str = Field(..., description="e.g., 'PAN Matching', 'Date Range Overlap'")
    status: str = Field(..., description="pass | warning | fail")
    details: str
    documents_compared: List[str] = Field(default_factory=list)
