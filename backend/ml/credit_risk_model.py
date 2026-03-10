"""
Credit Risk Model (XGBoost)
Stage 5 — 28-feature risk scoring with SHAP explainability (PRD 4.2).
"""

from typing import Any, Dict, List, Optional
from schemas.risk_score import RiskScoreResponse, SHAPExplanation
from schemas.common import RiskGrade
from ml.model_loader import get_model, model_registry
from ml.feature_engineering import FEATURE_NAMES, features_to_array
import numpy as np


# Risk grade thresholds (PD-based)
GRADE_THRESHOLDS = {
    "A": (0, 0.05),      # PD < 5%
    "B": (0.05, 0.15),   # PD 5-15%
    "C": (0.15, 0.30),   # PD 15-30%
    "D": (0.30, 0.50),   # PD 30-50%
    "E": (0.50, 1.0),    # PD > 50%
}

# Feature display labels
FEATURE_LABELS = {
    "current_ratio": "Current Ratio",
    "debt_to_equity": "Debt-to-Equity Ratio",
    "dscr": "Debt Service Coverage Ratio",
    "interest_coverage": "Interest Coverage",
    "ebitda_margin": "EBITDA Margin %",
    "roe": "Return on Equity",
    "revenue_cagr": "Revenue CAGR",
    "pat_margin": "PAT Margin %",
    "gst_vs_financial_ratio": "GST vs Financial Ratio",
    "filing_regularity": "GST Filing Regularity",
    "gstr_mismatch": "GSTR Mismatch %",
    "itc_ratio": "ITC Ratio",
    "circular_trading_score": "Circular Trading Score",
    "itc_reversals": "ITC Reversals",
    "bounce_rate": "Cheque Bounce Rate",
    "bounce_amount_ratio": "Bounce Amount Ratio",
    "cash_withdrawal_ratio": "Cash Withdrawal Ratio",
    "emi_burden": "EMI Burden Ratio",
    "balance_volatility": "Balance Volatility",
    "window_dressing_score": "Window Dressing Score",
    "collateral_coverage": "Collateral Coverage",
    "promoter_character_score": "Promoter Character",
    "management_quality_score": "Management Quality",
    "litigation_count": "Litigation Count",
    "sector_risk_weight": "Sector Risk Weight",
    "rbi_caution_flag": "RBI Caution Flag",
    "news_sentiment_score": "News Sentiment",
    "research_flag_count": "Research Red Flags",
}


def compute_credit_risk_score(
    application_id: str,
    features: Dict[str, float],
    include_shap: bool = True,
) -> RiskScoreResponse:
    """
    Compute XGBoost credit risk score.
    Returns risk grade, PD, SHAP values, and recommendations.
    """
    model = get_model("credit_risk")
    feature_array = np.array([features_to_array(features)])

    if model is not None:
        try:
            proba = model.predict_proba(feature_array)[0]
            pd_score = float(proba[1])  # Probability of default
        except Exception:
            pd_score = _rule_based_risk(features)
    else:
        pd_score = _rule_based_risk(features)

    # Map PD to risk grade
    risk_grade = _pd_to_grade(pd_score)
    final_score = (1 - pd_score) * 100  # Higher = better

    # SHAP explanation
    shap_values = []
    if include_shap:
        shap_values = _compute_shap(model, feature_array, features)

    top_risks = [s.feature_name for s in shap_values if s.direction == "increases_risk"][:3]
    top_strengths = [s.feature_name for s in shap_values if s.direction == "decreases_risk"][:3]

    # Rate and limit recommendations
    recommended_rate = _get_recommended_rate(risk_grade)
    recommended_limit = features.get("collateral_coverage", 1.0) * 0.75  # Placeholder

    return RiskScoreResponse(
        application_id=application_id,
        final_risk_score=round(final_score, 2),
        risk_grade=risk_grade,
        probability_of_default=round(pd_score, 4),
        recommended_rate=recommended_rate,
        recommended_limit=recommended_limit,
        shap_values=shap_values,
        top_risk_factors=top_risks,
        top_strengths=top_strengths,
        features_used=features,
        model_version="credit_risk_v1",
    )


def _pd_to_grade(pd: float) -> RiskGrade:
    """Map PD to risk grade."""
    for grade, (low, high) in GRADE_THRESHOLDS.items():
        if low <= pd < high:
            return RiskGrade(grade)
    return RiskGrade.E


def _get_recommended_rate(grade: RiskGrade) -> float:
    """Get recommended interest rate by grade."""
    rates = {"A": 9.5, "B": 11.0, "C": 13.0, "D": 15.5, "E": 18.0}
    return rates.get(grade.value, 14.0)


def _compute_shap(model, feature_array, features: Dict[str, float]) -> List[SHAPExplanation]:
    """Compute SHAP values for explainability."""
    explainer = model_registry.get_explainer("shap_explainer")

    if explainer is not None and model is not None:
        try:
            import shap
            shap_vals = explainer.shap_values(feature_array)
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]  # Class 1 (default)
            values = shap_vals[0]

            explanations = []
            for i, name in enumerate(FEATURE_NAMES):
                sv = float(values[i])
                explanations.append(SHAPExplanation(
                    feature_name=FEATURE_LABELS.get(name, name),
                    feature_value=features.get(name, 0),
                    shap_value=round(sv, 4),
                    direction="increases_risk" if sv > 0 else "decreases_risk",
                    display_label=FEATURE_LABELS.get(name, name),
                ))
            return sorted(explanations, key=lambda x: abs(x.shap_value), reverse=True)
        except Exception:
            pass

    # Fallback: synthetic SHAP values
    return _synthetic_shap(features)


def _synthetic_shap(features: Dict[str, float]) -> List[SHAPExplanation]:
    """Generate synthetic SHAP-like explanations when model not available."""
    explanations = []
    for name in FEATURE_NAMES:
        val = features.get(name, 0)
        # Simple heuristic
        if name in ["bounce_rate", "debt_to_equity", "circular_trading_score", "window_dressing_score", "sector_risk_weight"]:
            direction = "increases_risk" if val > 0.3 else "decreases_risk"
            sv = val * 0.1
        else:
            direction = "decreases_risk" if val > 0.5 else "increases_risk"
            sv = (0.5 - val) * 0.1

        explanations.append(SHAPExplanation(
            feature_name=FEATURE_LABELS.get(name, name),
            feature_value=round(val, 4),
            shap_value=round(sv, 4),
            direction=direction,
            display_label=FEATURE_LABELS.get(name, name),
        ))
    return sorted(explanations, key=lambda x: abs(x.shap_value), reverse=True)[:15]


def _rule_based_risk(features: Dict[str, float]) -> float:
    """Fallback PD estimation when model not available."""
    pd = 0.2  # Base PD 20%

    if features.get("current_ratio", 0) > 1.5:
        pd -= 0.05
    if features.get("debt_to_equity", 0) > 3.0:
        pd += 0.1
    if features.get("dscr", 0) > 1.5:
        pd -= 0.05
    if features.get("bounce_rate", 0) > 0.1:
        pd += 0.1
    if features.get("circular_trading_score", 0) > 50:
        pd += 0.15
    if features.get("rbi_caution_flag", 0) > 0:
        pd += 0.2
    if features.get("news_sentiment_score", 0) < 0.5:
        pd += 0.05

    return max(0.01, min(0.99, pd))


def run_what_if_scoring(application_id: str, adjusted_features: Dict[str, float]) -> Dict[str, Any]:
    """What-If: run scoring with adjusted features, compare to original."""
    # TODO: Load original features from DB, apply adjustments, re-score
    return {
        "original_score": 65.0,
        "adjusted_score": 70.0,
        "score_change": 5.0,
        "original_grade": "B",
        "adjusted_grade": "B",
        "message": "What-If simulation — placeholder. Will use actual model when .pkl available.",
    }
