"""
Banking Behavior Scorer
Stage 4 — 12-feature banking conduct scoring (PRD 4.4).

Features: Bounce frequency, bounce amount, cash withdrawal, EMI burden,
balance volatility, window dressing, credit concentration, account age,
active days, debit/credit ratio, average balance, highest bounce month.
"""

from typing import Any, Dict, List
from ml.model_loader import get_model
import numpy as np


BANKING_FEATURES = [
    "bounce_frequency",
    "bounce_amount_ratio",
    "cash_withdrawal_ratio",
    "emi_burden_ratio",
    "balance_volatility",
    "window_dressing_pattern",
    "credit_concentration",
    "account_age_months",
    "active_days_ratio",
    "debit_credit_ratio",
    "average_balance",
    "highest_bounce_month_amount",
]


def compute_banking_score(monthly_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute banking behavior score from 12-month bank statement data.
    Returns score 0-100 (higher = healthier account).
    """
    if not monthly_data:
        return {"banking_conduct_score": 50, "features": {}, "flags": []}

    features = _extract_banking_features(monthly_data)
    feature_array = np.array([[features.get(f, 0) for f in BANKING_FEATURES]])

    model = get_model("banking_scorer")
    if model is not None:
        try:
            proba = model.predict_proba(feature_array)[0]
            score = float(proba[1]) * 100  # Probability of healthy behavior
        except Exception:
            score = _rule_based_banking_score(features)
    else:
        score = _rule_based_banking_score(features)

    flags = _generate_banking_flags(features)

    return {
        "banking_conduct_score": round(score, 2),
        "features": features,
        "flags": flags,
        "risk_level": "low" if score >= 70 else "medium" if score >= 40 else "high",
    }


def _extract_banking_features(months: List[Dict[str, Any]]) -> Dict[str, float]:
    """Extract 12 features from monthly banking data."""
    n = len(months)
    total_bounces = sum(int(m.get("bounce_count", 0) or 0) for m in months)
    total_credits = sum(float(m.get("total_credits", 0) or 0) for m in months)
    total_debits = sum(float(m.get("total_debits", 0) or 0) for m in months)
    total_bounce_amt = sum(float(m.get("bounce_amount", 0) or 0) for m in months)
    total_cash = sum(float(m.get("cash_withdrawals", 0) or 0) for m in months)
    total_emi = sum(float(m.get("emi_outflows", 0) or 0) for m in months)
    balances = [float(m.get("closing_balance", 0) or 0) for m in months]
    avg_balances = [float(m.get("average_balance", 0) or 0) for m in months]
    bounce_amounts = [float(m.get("bounce_amount", 0) or 0) for m in months]

    return {
        "bounce_frequency": total_bounces / max(n, 1),
        "bounce_amount_ratio": total_bounce_amt / max(total_credits, 1),
        "cash_withdrawal_ratio": total_cash / max(total_credits, 1),
        "emi_burden_ratio": total_emi / max(total_credits, 1),
        "balance_volatility": float(np.std(balances)) / max(float(np.mean(balances)), 1) if balances else 0,
        "window_dressing_pattern": float(np.mean(balances)) / max(float(np.mean(avg_balances)), 1) - 1.0 if avg_balances else 0,
        "credit_concentration": max(float(m.get("total_credits", 0) or 0) for m in months) / max(total_credits / n, 1) if n > 0 else 0,
        "account_age_months": n,
        "active_days_ratio": sum(1 for m in months if float(m.get("total_credits", 0) or 0) > 0) / max(n, 1),
        "debit_credit_ratio": total_debits / max(total_credits, 1),
        "average_balance": float(np.mean(avg_balances)) if avg_balances else 0,
        "highest_bounce_month_amount": max(bounce_amounts) if bounce_amounts else 0,
    }


def _rule_based_banking_score(features: Dict[str, float]) -> float:
    """Fallback rule-based scoring."""
    score = 70.0
    if features.get("bounce_frequency", 0) > 3:
        score -= 20
    elif features.get("bounce_frequency", 0) > 1:
        score -= 10
    if features.get("cash_withdrawal_ratio", 0) > 0.5:
        score -= 15
    if features.get("emi_burden_ratio", 0) > 0.6:
        score -= 15
    if features.get("window_dressing_pattern", 0) > 0.3:
        score -= 10
    if features.get("balance_volatility", 0) > 1.5:
        score -= 10
    if features.get("active_days_ratio", 0) > 0.9:
        score += 10
    return max(0, min(100, score))


def _generate_banking_flags(features: Dict[str, float]) -> List[Dict[str, Any]]:
    """Generate banking red flags."""
    flags = []
    if features.get("bounce_frequency", 0) > 3:
        flags.append({"flag": "High Bounce Frequency", "severity": "high", "value": features["bounce_frequency"]})
    if features.get("cash_withdrawal_ratio", 0) > 0.5:
        flags.append({"flag": "High Cash Withdrawals", "severity": "medium", "value": features["cash_withdrawal_ratio"]})
    if features.get("window_dressing_pattern", 0) > 0.3:
        flags.append({"flag": "Window Dressing Pattern", "severity": "high", "value": features["window_dressing_pattern"]})
    if features.get("emi_burden_ratio", 0) > 0.6:
        flags.append({"flag": "High EMI Burden", "severity": "medium", "value": features["emi_burden_ratio"]})
    return flags
