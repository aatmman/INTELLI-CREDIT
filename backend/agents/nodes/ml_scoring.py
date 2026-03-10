"""
ML Scoring Node — Runs all 4 models in the LangGraph pipeline.

Models:
  1. Pre-Qualification   (Logistic Regression)
  2. Credit Risk          (XGBoost + SHAP)
  3. Banking Scorer       (Logistic Regression + time-series features)
  4. Circular Trading     (Isolation Forest + rule engine)

All models are loaded via the singleton ModelRegistry.
Results are written back to CreditApplicationState.
"""

from typing import Any, Dict, List
from agents.state import CreditApplicationState, SHAPValue
from ml.model_loader import ModelRegistry
from ml.pre_qual_model import run_pre_qual_scoring
from ml.credit_risk_model import compute_credit_risk_score
from ml.banking_scorer import compute_banking_score
from ml.circular_trading import detect_circular_trading
from ml.feature_engineering import build_xgboost_features
from schemas.pre_qual import PreQualFeatures


# ---------------------------------------------------------------------------
# Helper: safely extract a float from state with a default
# ---------------------------------------------------------------------------

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert a value to float, returning default on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 1. Pre-Qualification Scoring
# ---------------------------------------------------------------------------

def _run_pre_qual(state: CreditApplicationState) -> Dict[str, Any]:
    """
    Run the pre-qualification model.
    Extracts the 8 features from state and delegates to run_pre_qual_scoring.
    """
    features = PreQualFeatures(
        sector_risk_weight=_safe_float(state.get("sector", 1.0), 1.0),
        turnover_to_loan_ratio=(
            _safe_float(state.get("annual_turnover"), 1.0)
            / max(_safe_float(state.get("loan_amount_requested"), 1.0), 1.0)
        ),
        years_in_business=_safe_float(state.get("years_in_business"), 5),
        existing_debt_load_ratio=_safe_float(
            (state.get("balance_sheet") or {}).get("total_debt", 0), 0.0
        ) / max(_safe_float(state.get("annual_turnover"), 1.0), 1.0),
        npa_flag=int(bool(state.get("npa_flag", 0))),
        loan_type_feasibility=_safe_float(
            state.get("loan_type_feasibility"), 0.8
        ),
        company_incorporation_age=_safe_float(
            state.get("company_incorporation_age"), 5
        ),
        group_company_status=int(bool(state.get("group_company_status", 0))),
    )
    result = run_pre_qual_scoring(features)
    return {"pre_qual_score": result.score}


# ---------------------------------------------------------------------------
# 2. Credit Risk Scoring  (XGBoost + SHAP)
# ---------------------------------------------------------------------------

def _run_credit_risk(state: CreditApplicationState) -> Dict[str, Any]:
    """
    Build the 28-feature vector and run XGBoost credit risk scoring.
    """
    application_id = state.get("application_id", "unknown")

    # Build features — tries DB first, falls back to state data
    features = build_xgboost_features(application_id)

    # If feature engineering returned an empty dict, fill from state
    if not features:
        features = state.get("xgboost_features") or {}

    result = compute_credit_risk_score(
        application_id=application_id,
        features=features,
        include_shap=True,
    )

    # Convert SHAP explanations to state-compatible dicts
    shap_values: List[SHAPValue] = []
    for sv in (result.shap_values or []):
        shap_values.append(SHAPValue(
            feature_name=sv.feature_name,
            feature_value=sv.feature_value,
            shap_value=sv.shap_value,
            direction=sv.direction,
        ))

    return {
        "xgboost_features": features,
        "final_risk_score": result.final_risk_score,
        "risk_grade": result.risk_grade.value if hasattr(result.risk_grade, "value") else str(result.risk_grade),
        "probability_of_default": result.probability_of_default,
        "shap_values": shap_values,
        "top_risk_factors": result.top_risk_factors or [],
        "top_strengths": result.top_strengths or [],
        "recommended_limit": result.recommended_limit,
        "recommended_rate": result.recommended_rate,
    }


# ---------------------------------------------------------------------------
# 3. Banking Scorer
# ---------------------------------------------------------------------------

def _run_banking_scorer(state: CreditApplicationState) -> Dict[str, Any]:
    """
    Run the banking behavior scoring model on 12-month statement data.
    """
    monthly_data = state.get("banking_monthly_data") or []
    result = compute_banking_score(monthly_data)
    return {
        "banking_conduct_score": result.get("banking_conduct_score", 50.0),
        "banking_flags": result.get("flags", []),
    }


# ---------------------------------------------------------------------------
# 4. Circular Trading Detection  (Isolation Forest + Rules)
# ---------------------------------------------------------------------------

def _run_circular_trading(state: CreditApplicationState) -> Dict[str, Any]:
    """
    Run circular trading detection using GST, banking, and financial data.
    """
    gst_data = state.get("gst_monthly_data") or []
    banking_data = state.get("banking_monthly_data") or []

    # Build financial_data dict from state
    pnl = state.get("profit_and_loss") or {}
    financial_data: Dict[str, Any] = {
        "total_revenue": pnl.get("total_revenue", 0),
        "cost_of_goods": pnl.get("cost_of_goods", 0),
    }

    result = detect_circular_trading(gst_data, banking_data, financial_data)
    return {
        "circular_trading_score": result.get("circular_trading_score", 0),
        "circular_trading_flags": result.get("flags", []),
    }


# ---------------------------------------------------------------------------
# Main node entry point
# ---------------------------------------------------------------------------

async def ml_scoring_node(state: CreditApplicationState) -> CreditApplicationState:
    """
    LangGraph node — runs all 4 ML models sequentially:
      1. Pre-Qualification  (Logistic Regression)
      2. Credit Risk         (XGBoost + SHAP)
      3. Banking Scorer      (Logistic Regression)
      4. Circular Trading    (Isolation Forest)

    Each model is wrapped in try/except so a single failure
    does not block the rest of the pipeline.
    """
    # Ensure the ModelRegistry has loaded all .pkl files
    registry = ModelRegistry()
    registry.load_all()

    state["current_node"] = "ml_scoring"
    state["progress_percent"] = 75
    state["status_message"] = "Running ML models..."

    errors: list = list(state.get("errors") or [])

    # ── 1. Pre-Qualification ────────────────────────────────────
    try:
        state["status_message"] = "Running pre-qualification model..."
        pq = _run_pre_qual(state)
        state.update(pq)
    except Exception as exc:
        errors.append(f"[ml_scoring] pre_qual failed: {exc}")

    # ── 2. Credit Risk (XGBoost + SHAP) ────────────────────────
    try:
        state["status_message"] = "Running credit risk model (XGBoost + SHAP)..."
        cr = _run_credit_risk(state)
        state.update(cr)
    except Exception as exc:
        errors.append(f"[ml_scoring] credit_risk failed: {exc}")

    # ── 3. Banking Scorer ──────────────────────────────────────
    try:
        state["status_message"] = "Running banking scorer..."
        bs = _run_banking_scorer(state)
        state.update(bs)
    except Exception as exc:
        errors.append(f"[ml_scoring] banking_scorer failed: {exc}")

    # ── 4. Circular Trading (Isolation Forest) ─────────────────
    try:
        state["status_message"] = "Running circular trading detector..."
        ct = _run_circular_trading(state)
        state.update(ct)
    except Exception as exc:
        errors.append(f"[ml_scoring] circular_trading failed: {exc}")

    # ── Finalize ───────────────────────────────────────────────
    state["errors"] = errors
    state["status_message"] = "ML scoring complete."
    state["progress_percent"] = 80

    return state
