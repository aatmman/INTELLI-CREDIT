"""
Application management Pydantic schemas.
Core application CRUD + stage transitions.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from schemas.common import ApplicationStage, LoanType, RiskGrade


class ApplicationCreate(BaseModel):
    """Create a new loan application (after pre-qual passes)."""
    company_name: str
    cin_number: Optional[str] = None
    pan_number: Optional[str] = None
    sector: str
    loan_type: LoanType
    loan_amount_requested: float = Field(..., gt=0)
    annual_turnover: float = Field(..., gt=0)
    years_in_business: int = Field(..., ge=1)
    contact_email: str
    contact_phone: Optional[str] = None
    borrower_uid: str = Field(..., description="Firebase UID of borrower")
    pre_qual_score: Optional[float] = None
    pre_qual_data: Optional[Dict[str, Any]] = None


class ApplicationUpdate(BaseModel):
    """Partial update of application fields."""
    company_name: Optional[str] = None
    loan_amount_requested: Optional[float] = None
    assigned_rm: Optional[str] = None
    assigned_analyst: Optional[str] = None
    assigned_cm: Optional[str] = None
    remarks: Optional[str] = None


class ApplicationStageTransition(BaseModel):
    """Request to move application to next stage."""
    target_stage: ApplicationStage
    transitioned_by: Optional[str] = None
    remarks: Optional[str] = None


class ApplicationRecord(BaseModel):
    """Full application record from database."""
    id: str
    company_name: str
    cin_number: Optional[str] = None
    pan_number: Optional[str] = None
    sector: str
    loan_type: LoanType
    loan_amount_requested: float
    annual_turnover: float
    years_in_business: int
    contact_email: str
    contact_phone: Optional[str] = None
    
    # Stage tracking
    current_stage: ApplicationStage = ApplicationStage.PRE_QUALIFICATION
    stage_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Assignments
    borrower_uid: str
    assigned_rm: Optional[str] = None
    assigned_analyst: Optional[str] = None
    assigned_cm: Optional[str] = None
    
    # Scores
    pre_qual_score: Optional[float] = None
    final_risk_grade: Optional[RiskGrade] = None
    
    # Status
    is_active: bool = True
    remarks: Optional[str] = None
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ApplicationListItem(BaseModel):
    """Lightweight application info for dashboard lists."""
    id: str
    company_name: str
    sector: str
    loan_type: LoanType
    loan_amount_requested: float
    current_stage: ApplicationStage
    final_risk_grade: Optional[RiskGrade] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
