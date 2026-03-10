"""
Pre-Qualification Pydantic schemas.
Stage 0 — Instant eligibility check with 8 features.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from schemas.common import EligibilityTier, LoanType


class PreQualRequest(BaseModel):
    """Pre-qualification check request — 8 features as per PRD 4.1."""

    company_name: str = Field(..., description="Registered company name")
    cin_number: Optional[str] = Field(None, description="Company Identification Number")
    sector: str = Field(..., description="Industry sector (e.g., 'Manufacturing', 'NBFC')")
    annual_turnover: float = Field(..., gt=0, description="Annual turnover in INR lakhs")
    loan_amount_requested: float = Field(..., gt=0, description="Requested loan amount in INR lakhs")
    loan_type: LoanType = Field(..., description="Type of loan facility")
    years_in_business: int = Field(..., ge=1, le=100, description="Years of operation")
    existing_debt: float = Field(default=0, ge=0, description="Existing debt in INR lakhs")
    is_npa: bool = Field(default=False, description="Is the company flagged as NPA?")
    incorporation_year: int = Field(..., description="Year of company incorporation")
    is_group_company: bool = Field(default=False, description="Part of a group company?")

    # Contact info for application creation
    contact_email: str = Field(..., description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone")


class PreQualFeatures(BaseModel):
    """Engineered features passed to the pre-qual ML model."""

    sector_risk_weight: float = Field(..., ge=0.8, le=2.5)
    turnover_to_loan_ratio: float = Field(..., ge=0, le=5.0)
    years_in_business: int = Field(..., ge=1, le=100)
    existing_debt_load_ratio: float = Field(..., ge=0, le=10)
    npa_flag: int = Field(..., ge=0, le=1)
    loan_type_feasibility: float = Field(..., ge=0, le=1.0)
    company_incorporation_age: int = Field(..., ge=0, le=100)
    group_company_status: int = Field(..., ge=0, le=1)


class PreQualResponse(BaseModel):
    """Pre-qualification check response."""

    application_id: Optional[str] = None
    score: float = Field(..., ge=0, le=100, description="Eligibility score 0-100")
    eligibility_tier: EligibilityTier
    reasons: List[str] = Field(default_factory=list, description="Factors affecting eligibility")
    recommended_next_steps: List[str] = Field(default_factory=list)
    sector_risk_weight: Optional[float] = None
    model_version: str = "pre_qual_v1"
