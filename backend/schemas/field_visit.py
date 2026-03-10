"""
Field Visit Pydantic schemas.
Stage 3 — Field visit observations + qualitative risk adjustments.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


class FieldVisitSubmission(BaseModel):
    """Field visit submission request."""
    application_id: str
    visit_date: datetime
    visited_by: Optional[str] = None

    # Factory / Office observations
    capacity_utilization_percent: Optional[float] = Field(None, ge=0, le=100)
    factory_condition: Optional[str] = Field(None, description="excellent | good | average | poor")
    inventory_level: Optional[str] = Field(None, description="adequate | excess | low")
    machinery_condition: Optional[str] = Field(None, description="modern | adequate | outdated | non_functional")

    # Management observations
    management_cooperation: Optional[str] = Field(None, description="cooperative | evasive | hostile")
    management_quality: Optional[str] = Field(None, description="strong | adequate | weak")
    promoter_presence: bool = Field(default=True)

    # General observations
    observations: str = Field(..., description="Free-text field visit observations")
    neighborhood_info: Optional[str] = None
    employee_count_observed: Optional[int] = None

    # Media
    photo_urls: List[str] = Field(default_factory=list)
    voice_record_url: Optional[str] = None

    # Additional structured notes
    additional_notes: Optional[Dict[str, Any]] = None


class FieldVisitRecord(BaseModel):
    """Stored field visit record."""
    id: str
    application_id: str
    visit_date: datetime
    visited_by: Optional[str] = None
    capacity_utilization_percent: Optional[float] = None
    factory_condition: Optional[str] = None
    inventory_level: Optional[str] = None
    machinery_condition: Optional[str] = None
    management_cooperation: Optional[str] = None
    management_quality: Optional[str] = None
    promoter_presence: bool = True
    observations: str
    photo_urls: List[str] = Field(default_factory=list)
    voice_record_url: Optional[str] = None
    risk_adjustments: Optional[Dict[str, Any]] = None
    qualitative_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QualitativeRiskAdjustment(BaseModel):
    """Individual risk adjustment derived from field visit."""
    factor: str = Field(..., description="e.g., 'Capacity Utilization', 'Management Behavior'")
    observation: str
    risk_points: float = Field(..., description="Positive = more risk, Negative = less risk")
    confidence: float = Field(default=0.8, ge=0, le=1.0)
