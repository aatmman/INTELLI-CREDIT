"""
Decision Pydantic schemas.
Stages 5-6 — CM and Sanctioning Authority decisions.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from schemas.common import DecisionAction, RiskGrade


class DecisionRequest(BaseModel):
    """Decision submission by CM or Sanctioning Authority."""
    application_id: str
    action: DecisionAction
    decided_by_role: str = Field(..., description="credit_manager | sanctioning_authority")
    
    # Approved terms (if approving)
    approved_limit: Optional[float] = None
    approved_rate: Optional[float] = None
    approved_tenure_months: Optional[int] = None
    
    # Conditions
    conditions: List[str] = Field(default_factory=list)
    covenants: List[str] = Field(default_factory=list)
    
    # Rejection / Return
    rejection_reason: Optional[str] = None
    return_instructions: Optional[str] = None
    
    # Notes
    remarks: Optional[str] = None


class DecisionRecord(BaseModel):
    """Stored decision record."""
    id: str
    application_id: str
    action: DecisionAction
    decided_by: str
    decided_by_role: str
    decided_at: datetime
    
    # Terms
    approved_limit: Optional[float] = None
    approved_rate: Optional[float] = None
    approved_tenure_months: Optional[int] = None
    risk_grade: Optional[RiskGrade] = None
    
    # Conditions
    conditions: List[str] = Field(default_factory=list)
    covenants: List[str] = Field(default_factory=list)
    
    # Rejection / Return
    rejection_reason: Optional[str] = None
    return_instructions: Optional[str] = None
    remarks: Optional[str] = None


class SanctionLetterRequest(BaseModel):
    """Request to generate sanction letter."""
    application_id: str
    format: str = Field(default="docx", description="docx | pdf")


class SanctionLetterResponse(BaseModel):
    """Generated sanction letter details."""
    application_id: str
    letter_url: str
    format: str
    generated_at: datetime
    terms: Dict[str, Any] = Field(default_factory=dict)


class DecisionPackResponse(BaseModel):
    """One-screen Decision Pack for Sanctioning Authority (PRD Section 6)."""
    application_id: str
    
    # Borrower summary
    company_name: str
    sector: str
    loan_type: str
    loan_amount_requested: float
    
    # Risk assessment
    risk_grade: Optional[RiskGrade] = None
    probability_of_default: Optional[float] = None
    
    # Key 5 numbers
    key_numbers: Dict[str, float] = Field(default_factory=dict, description="Top 5 financial metrics")
    
    # SHAP-based factors
    top_risk_factors: List[str] = Field(default_factory=list, description="Top 3 from SHAP")
    top_strengths: List[str] = Field(default_factory=list, description="Top 3 from SHAP")
    
    # Policy
    policy_exceptions: List[str] = Field(default_factory=list)
    
    # Links
    cam_url: Optional[str] = None
    
    # Previous decisions
    cm_decision: Optional[DecisionRecord] = None
