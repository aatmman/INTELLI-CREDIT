"""
Common Pydantic models shared across all schemas.
"""

from pydantic import BaseModel, Field
from typing import Any, Generic, List, Optional, TypeVar
from datetime import datetime
from enum import Enum
import uuid


# --- Enums ---

class ApplicationStage(str, Enum):
    PRE_QUALIFICATION = "pre_qualification"        # Stage 0
    DOCUMENT_UPLOAD = "document_upload"             # Stage 1
    RM_REVIEW = "rm_review"                         # Stage 2
    FIELD_VISIT = "field_visit"                     # Stage 3
    CREDIT_ANALYSIS = "credit_analysis"             # Stage 4
    CM_REVIEW = "cm_review"                         # Stage 5
    SANCTIONING = "sanctioning"                     # Stage 6
    POST_SANCTION = "post_sanction"                 # Stage 7


class RiskGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class LoanType(str, Enum):
    CASH_CREDIT = "CC"
    TERM_LOAN = "TL"
    WORKING_CAPITAL_TERM_LOAN = "WCTL"
    BANK_GUARANTEE = "BG"
    LETTER_OF_CREDIT = "LC"


class DecisionAction(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_MODIFICATIONS = "approve_with_modifications"
    REJECT = "reject"
    RETURN_FOR_REVIEW = "return_for_review"
    RETURN_FOR_DD = "return_for_dd"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    EXTRACTION_FAILED = "extraction_failed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class EligibilityTier(str, Enum):
    ELIGIBLE = "eligible"
    BORDERLINE = "borderline"
    NOT_ELIGIBLE = "not_eligible"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Base Models ---

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool = True
    message: str = "OK"
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


T = TypeVar("T")


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    items: List[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    message: str
    errors: Optional[List[str]] = None
    error_code: Optional[str] = None


class AuditInfo(BaseModel):
    """Common audit fields."""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
