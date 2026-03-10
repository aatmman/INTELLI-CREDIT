"""
Risk Score Pydantic schemas.
Stage 5 — XGBoost credit risk scoring + SHAP explainability.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from schemas.common import RiskGrade


class RiskScoreComputeRequest(BaseModel):
    """Request to compute risk score for an application."""
    application_id: str
    include_shap: bool = Field(default=True, description="Include SHAP explanation")
    model_version: Optional[str] = Field(default=None, description="Override model version")


class SHAPExplanation(BaseModel):
    """SHAP feature importance explanation."""
    feature_name: str
    feature_value: float
    shap_value: float
    direction: str = Field(..., description="increases_risk | decreases_risk")
    display_label: Optional[str] = None


class RiskScoreResponse(BaseModel):
    """Complete risk score output."""
    application_id: str
    
    # Pre-qual score (Stage 0)
    pre_qual_score: Optional[float] = None
    
    # Financial scores (Stage 4)
    financial_score: Optional[float] = None
    gst_score: Optional[float] = None
    banking_conduct_score: Optional[float] = None
    circular_trading_score: Optional[float] = None
    
    # XGBoost final score (Stage 5)
    final_risk_score: Optional[float] = Field(None, ge=0, le=100)
    risk_grade: Optional[RiskGrade] = None
    probability_of_default: Optional[float] = Field(None, ge=0, le=1.0, description="PD %")
    
    # Recommendations
    recommended_limit: Optional[float] = None
    recommended_rate: Optional[float] = None
    recommended_tenure_months: Optional[int] = None
    
    # SHAP
    shap_values: List[SHAPExplanation] = Field(default_factory=list)
    top_risk_factors: List[str] = Field(default_factory=list, description="Top 3 risk increasing factors")
    top_strengths: List[str] = Field(default_factory=list, description="Top 3 risk decreasing factors")
    
    # 28 features used
    features_used: Optional[Dict[str, float]] = None
    
    # Metadata
    model_version: str = "credit_risk_v1"
    scored_at: Optional[datetime] = None


class PolicyCheckResult(BaseModel):
    """Single policy rule check result."""
    rule_id: str
    rule_name: str
    rule_description: str
    status: str = Field(..., description="pass | warning | fail | exception")
    actual_value: Optional[str] = None
    threshold_value: Optional[str] = None
    is_hard_rule: bool = False
    exception_notes: Optional[str] = None


class PolicyCheckResponse(BaseModel):
    """Full policy compliance check."""
    application_id: str
    checks: List[PolicyCheckResult] = Field(default_factory=list)
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    exceptions: int = 0
    overall_status: str = Field(default="pending", description="compliant | non_compliant | exceptions_noted")
