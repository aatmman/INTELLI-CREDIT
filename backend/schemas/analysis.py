"""
Analysis Pydantic schemas.
Stage 4 — Financial, GST, Banking, Research, Timeline data.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from schemas.common import Severity


# --- Financial Analysis ---

class FinancialRatios(BaseModel):
    """Financial ratios for a single year."""
    financial_year: str
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    dscr: Optional[float] = None  # Debt Service Coverage Ratio
    interest_coverage: Optional[float] = None
    ebitda_margin: Optional[float] = None
    roe: Optional[float] = None  # Return on Equity
    revenue_cagr: Optional[float] = None
    pat_margin: Optional[float] = None  # Profit After Tax %
    net_worth: Optional[float] = None
    total_revenue: Optional[float] = None
    total_debt: Optional[float] = None
    ebitda: Optional[float] = None
    pat: Optional[float] = None
    cfo: Optional[float] = None  # Cash Flow from Operations


class ExtractedFinancials(BaseModel):
    """3-year extracted financial data."""
    application_id: str
    financials: List[FinancialRatios] = Field(default_factory=list)
    balance_sheet: Optional[Dict[str, Any]] = None
    profit_and_loss: Optional[Dict[str, Any]] = None
    cash_flow: Optional[Dict[str, Any]] = None
    sector_benchmarks: Optional[Dict[str, Any]] = None
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)


# --- GST Analysis ---

class GSTMonthlyEntry(BaseModel):
    """Single month GST data."""
    month: str  # "2024-01"
    gstr3b_turnover: Optional[float] = None
    gstr1_turnover: Optional[float] = None
    itc_claimed: Optional[float] = None
    itc_available: Optional[float] = None
    itc_reversal: Optional[float] = None
    tax_paid: Optional[float] = None
    filing_status: Optional[str] = None  # filed | late | not_filed
    mismatch_amount: Optional[float] = None


class GSTAnalysisResponse(BaseModel):
    """GST analysis results."""
    application_id: str
    monthly_data: List[GSTMonthlyEntry] = Field(default_factory=list)
    gst_vs_financial_ratio: Optional[float] = None
    filing_regularity_score: Optional[float] = None
    gstr_mismatch_percent: Optional[float] = None
    itc_ratio: Optional[float] = None
    circular_trading_score: Optional[float] = None
    itc_reversals_flag: bool = False
    flags: List[Dict[str, Any]] = Field(default_factory=list)


# --- Banking Analysis ---

class BankingMonthlyEntry(BaseModel):
    """Single month banking data."""
    month: str
    total_credits: Optional[float] = None
    total_debits: Optional[float] = None
    closing_balance: Optional[float] = None
    average_balance: Optional[float] = None
    bounce_count: Optional[int] = None
    bounce_amount: Optional[float] = None
    cash_withdrawals: Optional[float] = None
    emi_outflows: Optional[float] = None


class BankingAnalysisResponse(BaseModel):
    """Banking analysis results."""
    application_id: str
    monthly_data: List[BankingMonthlyEntry] = Field(default_factory=list)
    bounce_rate: Optional[float] = None
    bounce_amount_ratio: Optional[float] = None
    cash_withdrawal_ratio: Optional[float] = None
    emi_burden_ratio: Optional[float] = None
    balance_volatility: Optional[float] = None
    window_dressing_flag: bool = False
    banking_conduct_score: Optional[float] = None
    flags: List[Dict[str, Any]] = Field(default_factory=list)


# --- Research Findings ---

class ResearchFinding(BaseModel):
    """Single research finding from external sources."""
    id: Optional[str] = None
    source: str = Field(..., description="tavily | mca | ecourts | rbi | sector_news")
    title: str
    summary: str
    url: Optional[str] = None
    published_date: Optional[datetime] = None
    severity: Severity = Severity.LOW
    risk_impact: Optional[str] = Field(None, description="Description of how this impacts risk")
    risk_points: float = Field(default=0, description="Risk score adjustment")
    category: Optional[str] = Field(None, description="news | legal | regulatory | financial")


class ResearchResponse(BaseModel):
    """Full research output for an application."""
    application_id: str
    findings: List[ResearchFinding] = Field(default_factory=list)
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    overall_research_risk: Optional[str] = None
    research_completed_at: Optional[datetime] = None


# --- Risk Timeline ---

class TimelineEvent(BaseModel):
    """Single event in the risk timeline."""
    date: datetime
    source: str = Field(..., description="financial | gst | banking | research | field_visit")
    event_type: str
    title: str
    description: str
    severity: Severity = Severity.LOW
    risk_points: float = Field(default=0)
    raw_data: Optional[Dict[str, Any]] = None


class RiskTimelineResponse(BaseModel):
    """Chronological red flag timeline — key differentiator."""
    application_id: str
    events: List[TimelineEvent] = Field(default_factory=list)
    total_events: int = 0
    critical_events: int = 0
    timeline_risk_score: Optional[float] = None
    generated_at: Optional[datetime] = None


# --- What-If Simulator ---

class WhatIfRequest(BaseModel):
    """Adjust inputs to see score changes."""
    application_id: str
    adjusted_features: Dict[str, float] = Field(
        ..., description="Feature name → new value pairs"
    )


class WhatIfResponse(BaseModel):
    """Score change comparison."""
    original_score: float
    adjusted_score: float
    score_change: float
    original_grade: str
    adjusted_grade: str
    feature_impacts: List[Dict[str, Any]] = Field(default_factory=list)
