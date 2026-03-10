"""
CreditApplicationState — Full TypedDict for LangGraph state machine.
Contains all fields for every node in the CreditAppraisalGraph.
"""

from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime


class ResearchFinding(TypedDict, total=False):
    """Single research finding."""
    source: str          # tavily | mca | ecourts | rbi | sector_news
    source_type: str     # news | mca | ecourts | rbi | sector
    title: str
    summary: str
    url: str
    published_date: str
    severity: str        # low | medium | high | critical
    risk_impact: float
    risk_points: float
    category: str
    reviewed_by_analyst: bool


class TimelineEvent(TypedDict, total=False):
    """Single timeline event."""
    date: str
    source: str          # financial | gst | banking | research | field_visit | policy
    event_type: str
    title: str
    description: str
    severity: str
    risk_points: float
    risk_impact: float
    source_url: Optional[str]


class SHAPValue(TypedDict, total=False):
    """SHAP explanation value."""
    feature_name: str
    feature_value: float
    shap_value: float
    direction: str       # increases_risk | decreases_risk


class CreditApplicationState(TypedDict, total=False):
    """
    Complete state for the CreditAppraisalGraph.
    Checkpointed in Supabase for crash recovery.
    """

    # --- Application Identity ---
    application_id: str
    company_name: str
    cin_number: str
    pan_number: str
    sector: str
    loan_type: str
    loan_amount_requested: float
    annual_turnover: float
    years_in_business: float

    # --- Stage Tracking ---
    current_stage: str
    current_node: str
    progress_percent: float
    status_message: str

    # --- Document Ingestion (Agent 1) ---
    documents: List[Dict[str, Any]]
    parsed_documents: List[Dict[str, Any]]
    extraction_results: Dict[str, Any]
    parsing_errors: List[str]
    cross_validation_results: List[Dict[str, Any]]

    # --- KYC / ITR / Collateral / Miscellaneous data ---
    kyc_data: List[Dict[str, Any]]
    itr_data: Dict[str, Any]
    collateral_data: Dict[str, Any]
    miscellaneous_data: Dict[str, Any]

    # --- Financial Extraction (Agent 1 continued) ---
    balance_sheet: Dict[str, Any]
    profit_and_loss: Dict[str, Any]
    cash_flow: Dict[str, Any]
    financial_ratios: List[Dict[str, Any]]  # 3-year ratios

    # --- GST Analysis (Agent subset) ---
    gst_monthly_data: List[Dict[str, Any]]  # 24 months
    gst_flags: List[Dict[str, Any]]
    gst_vs_financial_ratio: float
    circular_trading_score: float
    circular_trading_flags: List[Dict[str, Any]]

    # --- Banking Analysis (Agent subset) ---
    banking_monthly_data: List[Dict[str, Any]]  # 12 months
    banking_flags: List[Dict[str, Any]]
    banking_conduct_score: float
    window_dressing_detected: bool

    # --- Field Visit / Qualitative (Agent 3) ---
    field_visit_notes: str
    field_visit_structured: Dict[str, Any]
    qualitative_risk_adjustments: List[Dict[str, Any]]
    qualitative_score: float
    qualitative_risk_adjustment: float
    field_visit_summary: str
    management_quality_score: float

    # --- Research (Agent 2) ---
    company_news: List[ResearchFinding]
    mca_findings: List[ResearchFinding]
    ecourts_findings: List[ResearchFinding]
    rbi_list_findings: List[ResearchFinding]
    sector_research: List[ResearchFinding]
    all_research_findings: List[ResearchFinding]  # Aggregated + deduped
    research_risk_score: float
    external_risk_score: float
    research_summary: str

    # --- Anomaly Detection (Agent 4) ---
    financial_anomalies: List[Dict[str, Any]]
    anomaly_flags: List[Dict[str, Any]]      # Alias used by some nodes
    anomaly_score: float

    # --- Risk Timeline (Agent 5 — DIFFERENTIATOR) ---
    timeline_events: List[TimelineEvent]
    timeline_risk_score: float
    risk_timeline: List[TimelineEvent]       # Alias

    # --- ML Scoring (Agent/Model integration) ---
    pre_qual_score: float
    xgboost_features: Dict[str, float]  # 28 features
    final_risk_score: float
    risk_grade: str                      # A-E
    probability_of_default: float
    shap_values: List[SHAPValue]
    top_risk_factors: List[str]
    top_strengths: List[str]
    recommended_limit: float
    recommended_rate: float

    # --- Policy Check (Agent 7) ---
    policy_check_results: List[Dict[str, Any]]
    policy_results: List[Dict[str, Any]]     # Alias
    policy_exceptions: List[str]
    policy_overall_status: str
    policy_exception_required: bool

    # --- CAM (Agent 6) ---
    cam_narrative: str
    cam_sections: Dict[str, str]
    cam_content: Dict[str, Any]
    cam_citations: List[Dict[str, str]]
    cam_document_url: str
    cam_docx_url: str
    cam_pdf_url: str

    # --- Sanction Letter (Agent 8) ---
    sanction_letter_url: str
    rejection_letter_url: str

    # --- Decision ---
    decision: str                        # approve | reject | modify
    decision_by: str
    decision_remarks: str
    conditions: List[str]

    # --- Metadata ---
    errors: List[str]
    warnings: List[str]
    started_at: str
    completed_at: str
    last_checkpoint: str
