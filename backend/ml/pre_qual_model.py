"""
Pre-Qualification Model (Logistic Regression)
Stage 0 — 8-feature eligibility scoring (PRD 4.1).
"""

from typing import Optional
from schemas.pre_qual import PreQualFeatures, PreQualResponse
from schemas.common import EligibilityTier
from ml.model_loader import get_model
import numpy as np


def run_pre_qual_scoring(features) -> PreQualResponse:
    """
    Run pre-qualification scoring.
    Uses trained Logistic Regression model if available, otherwise rule-based fallback.
    Accepts both PreQualFeatures Pydantic objects and plain dicts.
    """
    if isinstance(features, dict):
        features = PreQualFeatures(**features)
    model = get_model("pre_qual")
    feature_array = np.array([[
        features.sector_risk_weight,
        features.turnover_to_loan_ratio,
        features.years_in_business,
        features.existing_debt_load_ratio,
        features.npa_flag,
        features.loan_type_feasibility,
        features.company_incorporation_age,
        features.group_company_status,
    ]])

    if model is not None:
        # Use trained model
        try:
            proba = model.predict_proba(feature_array)[0]
            score = float(proba[1]) * 100  # Probability of class 1 (eligible)
        except Exception:
            score = _rule_based_scoring(features)
    else:
        # Rule-based fallback when model .pkl not yet available
        score = _rule_based_scoring(features)

    # Determine eligibility tier
    if score >= 65:
        tier = EligibilityTier.ELIGIBLE
    elif score >= 40:
        tier = EligibilityTier.BORDERLINE
    else:
        tier = EligibilityTier.NOT_ELIGIBLE

    # Generate reasons
    reasons = _generate_reasons(features, score)
    next_steps = _generate_next_steps(tier)

    return PreQualResponse(
        score=round(score, 2),
        eligibility_tier=tier,
        reasons=reasons,
        recommended_next_steps=next_steps,
    )


def _rule_based_scoring(features: PreQualFeatures) -> float:
    """Fallback rule-based scoring when model is not available."""
    score = 50.0  # Base score

    # Sector risk (lower weight = better)
    if features.sector_risk_weight <= 1.0:
        score += 15
    elif features.sector_risk_weight >= 2.0:
        score -= 20

    # Turnover-to-loan ratio (higher = better)
    if features.turnover_to_loan_ratio >= 2.0:
        score += 15
    elif features.turnover_to_loan_ratio < 1.0:
        score -= 15

    # Years in business
    if features.years_in_business >= 10:
        score += 10
    elif features.years_in_business < 3:
        score -= 15

    # Debt load
    if features.existing_debt_load_ratio > 3.0:
        score -= 20
    elif features.existing_debt_load_ratio < 1.0:
        score += 10

    # NPA flag
    if features.npa_flag == 1:
        score -= 40

    # Loan type feasibility
    score += (features.loan_type_feasibility - 0.8) * 20

    # Company age
    if features.company_incorporation_age >= 10:
        score += 5

    # Group company
    if features.group_company_status == 1:
        score += 5

    return max(0, min(100, score))


def _generate_reasons(features: PreQualFeatures, score: float) -> list:
    """Generate human-readable reasons for the score."""
    reasons = []
    if features.npa_flag == 1:
        reasons.append("Company has NPA flag — significant negative impact")
    if features.sector_risk_weight >= 2.0:
        reasons.append(f"High-risk sector (weight: {features.sector_risk_weight})")
    if features.turnover_to_loan_ratio < 1.0:
        reasons.append("Loan amount exceeds annual turnover")
    if features.existing_debt_load_ratio > 3.0:
        reasons.append("High existing debt relative to turnover")
    if features.years_in_business < 3:
        reasons.append("Company has limited operational history")
    if features.turnover_to_loan_ratio >= 2.0:
        reasons.append("Healthy turnover-to-loan ratio")
    if features.years_in_business >= 10:
        reasons.append("Established business track record")
    return reasons


def _generate_next_steps(tier: EligibilityTier) -> list:
    """Generate recommended next steps."""
    if tier == EligibilityTier.ELIGIBLE:
        return ["Proceed to document upload", "Upload required financial documents"]
    elif tier == EligibilityTier.BORDERLINE:
        return ["Review may take longer", "Consider providing additional collateral documentation"]
    else:
        return ["Application does not meet minimum criteria", "Consider reapplying after improving financials"]
