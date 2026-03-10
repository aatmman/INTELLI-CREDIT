"""
Circular Trading Detection Model (Isolation Forest + Rules)
Stage 4 — GST fraud detection (PRD 4.3).

Detection Rules:
- GST Turnover Mismatch (>20% = +35 pts, >40% = +65 pts)
- ITC Reversal (>1.2x available = +40 pts)
- Round-Tripping (<5% margin high buy/sell = +30 pts)
- Bank Credit vs GST (<0.6x = +25 pts, >1.8x = +40 pts)
- Isolation Forest (anomaly score <-0.5 = +25 pts)
"""

from typing import Any, Dict, List
from ml.model_loader import get_model
import numpy as np


def detect_circular_trading(
    gst_data: List[Dict[str, Any]],
    banking_data: List[Dict[str, Any]],
    financial_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run circular trading detection using rules + Isolation Forest.
    Returns score 0-100 and specific flags.
    """
    score = 0
    flags = []

    # --- Rule 1: GST Turnover Mismatch ---
    total_3b = sum(float(m.get("gstr3b_turnover", 0) or 0) for m in gst_data)
    total_1 = sum(float(m.get("gstr1_turnover", 0) or 0) for m in gst_data)
    if total_3b > 0:
        mismatch = abs(total_3b - total_1) / total_3b
        if mismatch > 0.4:
            score += 65
            flags.append({"rule": "GST Turnover Mismatch", "severity": "critical", "detail": f"GSTR-3B vs GSTR-1 mismatch: {mismatch*100:.1f}%", "points": 65})
        elif mismatch > 0.2:
            score += 35
            flags.append({"rule": "GST Turnover Mismatch", "severity": "high", "detail": f"GSTR-3B vs GSTR-1 mismatch: {mismatch*100:.1f}%", "points": 35})

    # --- Rule 2: ITC Reversal ---
    total_itc_claimed = sum(float(m.get("itc_claimed", 0) or 0) for m in gst_data)
    total_itc_available = sum(float(m.get("itc_available", 0) or 0) for m in gst_data)
    if total_itc_available > 0 and total_itc_claimed > total_itc_available * 1.2:
        score += 40
        flags.append({"rule": "ITC Reversal", "severity": "high", "detail": f"ITC claimed ({total_itc_claimed:.0f}) exceeds 1.2x available ({total_itc_available:.0f})", "points": 40})

    # --- Rule 3: Round-Tripping ---
    fin_revenue = float(financial_data.get("total_revenue", 0) or 0)
    fin_cogs = float(financial_data.get("cost_of_goods", 0) or 0)
    if fin_revenue > 0 and fin_cogs > 0:
        margin = (fin_revenue - fin_cogs) / fin_revenue
        if margin < 0.05 and fin_revenue > 1000:  # <5% margin on high revenue
            score += 30
            flags.append({"rule": "Round-Tripping", "severity": "high", "detail": f"Very low margin ({margin*100:.1f}%) on high revenue — potential round-tripping", "points": 30})

    # --- Rule 4: Bank Credit vs GST ---
    total_bank_credits = sum(float(m.get("total_credits", 0) or 0) for m in banking_data)
    if total_3b > 0:
        bank_gst_ratio = total_bank_credits / total_3b
        if bank_gst_ratio < 0.6:
            score += 25
            flags.append({"rule": "Bank-GST Mismatch", "severity": "medium", "detail": f"Bank credits only {bank_gst_ratio:.2f}x of GST turnover", "points": 25})
        elif bank_gst_ratio > 1.8:
            score += 40
            flags.append({"rule": "Bank-GST Mismatch", "severity": "high", "detail": f"Bank credits {bank_gst_ratio:.2f}x GST turnover — inflated banking", "points": 40})

    # --- Rule 5: Isolation Forest ---
    iso_model = get_model("circular_trading")
    if iso_model is not None and gst_data:
        try:
            features = _build_iso_features(gst_data, banking_data)
            anomaly_score = iso_model.score_samples(np.array([features]))[0]
            if anomaly_score < -0.5:
                score += 25
                flags.append({"rule": "Isolation Forest Anomaly", "severity": "high", "detail": f"Anomaly score: {anomaly_score:.3f}", "points": 25})
        except Exception:
            pass

    return {
        "circular_trading_score": min(score, 100),
        "flags": flags,
        "total_flags": len(flags),
        "risk_level": "critical" if score >= 70 else "high" if score >= 40 else "medium" if score >= 20 else "low",
    }


def _build_iso_features(gst_data: list, banking_data: list) -> list:
    """Build feature vector for Isolation Forest."""
    total_3b = sum(float(m.get("gstr3b_turnover", 0) or 0) for m in gst_data)
    total_1 = sum(float(m.get("gstr1_turnover", 0) or 0) for m in gst_data)
    total_itc = sum(float(m.get("itc_claimed", 0) or 0) for m in gst_data)
    total_credits = sum(float(m.get("total_credits", 0) or 0) for m in banking_data)

    return [
        total_3b,
        total_1,
        abs(total_3b - total_1) / max(total_3b, 1),
        total_itc / max(total_3b, 1),
        total_credits / max(total_3b, 1),
    ]
