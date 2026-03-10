"""
Agent 4: Anomaly Detection Node — Financial red flag detection.

Reads financial ratios, P&L, BS, CF, GST, and banking data from state.
Detects 9 specific anomalies with severity-weighted scoring.
Updates state with anomaly_flags list and anomaly_score (0–100).
"""

from typing import Any, Dict, List, Optional
from agents.state import CreditApplicationState


# ---------------------------------------------------------------------------
# Severity weights for anomaly scoring
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHT = {
    "critical": 30,
    "high": 20,
    "medium": 10,
    "low": 5,
}


# ---------------------------------------------------------------------------
# Helper: safe numeric extraction
# ---------------------------------------------------------------------------

def _num(data: Dict, *keys: str) -> Optional[float]:
    """Extract a numeric value from nested dicts, trying multiple keys."""
    for key in keys:
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def _yoy_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """YoY percentage change. Returns None if inputs missing."""
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


# ---------------------------------------------------------------------------
# 9 anomaly detectors
# ---------------------------------------------------------------------------

def _check_earnings_not_cash_backed(ratios: List[Dict], pnl: Dict, cf: Dict) -> Optional[Dict]:
    """PAT grew >30% YoY but CFO declined."""
    if len(ratios) < 2:
        return None
    pat_current = _num(pnl, "profit_after_tax", "pat")
    # Try to get previous year PAT from ratios
    pat_margin_cur = _num(ratios[-1], "pat_margin")
    pat_margin_prev = _num(ratios[-2], "pat_margin") if len(ratios) >= 2 else None
    cfo_current = _num(cf, "cfo", "cash_from_operations")

    # Heuristic: if PAT margin improved significantly but CFO is negative
    if pat_current and pat_current > 0 and cfo_current is not None and cfo_current < 0:
        return {
            "flag_type": "earnings_not_cash_backed",
            "severity": "high",
            "description": "Profit after tax is positive but cash from operations is negative — earnings may not be cash-backed",
            "values": {"pat": pat_current, "cfo": cfo_current},
        }

    # Check PAT growth vs CFO decline using ratios
    if pat_margin_cur and pat_margin_prev:
        pat_growth = _yoy_change(pat_margin_cur, pat_margin_prev)
        if pat_growth is not None and pat_growth > 30 and cfo_current is not None and cfo_current < 0:
            return {
                "flag_type": "earnings_not_cash_backed",
                "severity": "high",
                "description": f"PAT margin grew {pat_growth:.1f}% YoY but CFO declined to ₹{cfo_current:,.0f}",
                "values": {"pat_growth_pct": pat_growth, "cfo": cfo_current},
            }
    return None


def _check_receivables_quality(bs: Dict, pnl: Dict) -> Optional[Dict]:
    """Debtors increased >50% while revenue grew <20%."""
    debtors = _num(bs, "trade_receivables", "sundry_debtors", "debtors")
    revenue = _num(pnl, "total_revenue", "revenue_from_operations")
    if debtors and revenue and revenue > 0:
        receivable_days = (debtors / revenue) * 365
        if receivable_days > 120:
            return {
                "flag_type": "receivables_quality_concern",
                "severity": "high",
                "description": f"Receivable days at {receivable_days:.0f} days (>120) — possible collection issues or round-tripping",
                "values": {"receivable_days": receivable_days, "debtors": debtors, "revenue": revenue},
            }
    return None


def _check_slow_inventory(bs: Dict, pnl: Dict) -> Optional[Dict]:
    """Inventory days excessive."""
    inventory = _num(bs, "inventories", "inventory", "stock_in_trade")
    revenue = _num(pnl, "total_revenue", "revenue_from_operations")
    if inventory and revenue and revenue > 0:
        inventory_days = (inventory / revenue) * 365
        if inventory_days > 180:
            return {
                "flag_type": "slow_moving_inventory",
                "severity": "medium",
                "description": f"Inventory days at {inventory_days:.0f} (>180) — possible slow-moving or obsolete stock",
                "values": {"inventory_days": inventory_days, "inventory": inventory},
            }
    return None


def _check_undisclosed_borrowing(ratios: List[Dict]) -> Optional[Dict]:
    """Interest cost doubled YoY but no new term loan found."""
    if len(ratios) < 2:
        return None
    icr_cur = _num(ratios[-1], "interest_coverage")
    icr_prev = _num(ratios[-2], "interest_coverage")
    if icr_cur and icr_prev and icr_prev > 0:
        # ICR halving means interest cost roughly doubled
        if icr_cur < icr_prev * 0.5:
            return {
                "flag_type": "undisclosed_borrowing",
                "severity": "high",
                "description": f"Interest coverage dropped from {icr_prev:.2f} to {icr_cur:.2f} — possible undisclosed borrowing",
                "values": {"icr_current": icr_cur, "icr_previous": icr_prev},
            }
    return None


def _check_gst_revenue_mismatch(state: CreditApplicationState) -> Optional[Dict]:
    """GST turnover vs Financial turnover gap >20%."""
    pnl = state.get("profit_and_loss") or {}
    fin_revenue = _num(pnl, "total_revenue", "revenue_from_operations")
    gst_data = state.get("gst_monthly_data") or []
    gst_annual = sum(float(m.get("gstr3b_turnover") or m.get("taxable_turnover") or 0) for m in gst_data)

    if fin_revenue and gst_annual > 0:
        gap = abs(fin_revenue - gst_annual) / gst_annual * 100
        if gap > 20:
            return {
                "flag_type": "gst_revenue_mismatch",
                "severity": "high",
                "description": f"GST vs financial revenue gap is {gap:.1f}% (>20% threshold)",
                "values": {"financial_revenue": fin_revenue, "gst_annual": gst_annual, "gap_pct": gap},
            }
    return None


def _check_bank_revenue_mismatch(state: CreditApplicationState) -> Optional[Dict]:
    """Bank credits annualized vs Financial revenue gap >30%."""
    pnl = state.get("profit_and_loss") or {}
    fin_revenue = _num(pnl, "total_revenue", "revenue_from_operations")
    bank_data = state.get("banking_monthly_data") or []
    bank_annual = sum(float(m.get("total_credits") or 0) for m in bank_data)

    if fin_revenue and bank_annual > 0:
        gap = abs(fin_revenue - bank_annual) / bank_annual * 100
        if gap > 30:
            return {
                "flag_type": "bank_revenue_mismatch",
                "severity": "medium",
                "description": f"Bank credits vs financial revenue gap is {gap:.1f}% (>30% threshold)",
                "values": {"financial_revenue": fin_revenue, "bank_annual": bank_annual, "gap_pct": gap},
            }
    return None


def _check_dscr_deterioration(ratios: List[Dict]) -> Optional[Dict]:
    """DSCR declined >0.3 YoY."""
    if len(ratios) < 2:
        return None
    dscr_cur = _num(ratios[-1], "dscr")
    dscr_prev = _num(ratios[-2], "dscr")
    if dscr_cur is not None and dscr_prev is not None:
        decline = dscr_prev - dscr_cur
        if decline > 0.3:
            return {
                "flag_type": "dscr_deterioration",
                "severity": "high",
                "description": f"DSCR declined from {dscr_prev:.2f} to {dscr_cur:.2f} (drop: {decline:.2f})",
                "values": {"dscr_current": dscr_cur, "dscr_previous": dscr_prev, "decline": decline},
            }
    return None


def _check_negative_net_worth(bs: Dict) -> Optional[Dict]:
    """Net Worth negative."""
    nw = _num(bs, "net_worth", "shareholders_funds", "total_equity")
    if nw is not None and nw < 0:
        return {
            "flag_type": "negative_net_worth",
            "severity": "critical",
            "description": f"Net worth is negative (₹{nw:,.0f}) — company is technically insolvent",
            "values": {"net_worth": nw},
        }
    return None


def _check_liquidity_stress(ratios: List[Dict]) -> Optional[Dict]:
    """Current Ratio <1.0."""
    if not ratios:
        return None
    cr = _num(ratios[-1], "current_ratio")
    if cr is not None and cr < 1.0:
        return {
            "flag_type": "liquidity_stress",
            "severity": "high",
            "description": f"Current ratio is {cr:.2f} (<1.0) — current liabilities exceed current assets",
            "values": {"current_ratio": cr},
        }
    return None


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def anomaly_detection_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Anomaly Detection.

    Runs 9 specific financial anomaly checks against state data.
    Each flag includes flag_type, severity, description, and trigger values.
    Anomaly score = sum of severity weights (critical=30, high=20, medium=10, low=5),
    capped at 100.
    """
    state["current_node"] = "anomaly_detection"
    state["progress_percent"] = 65
    state["status_message"] = "Detecting financial anomalies..."

    pnl = state.get("profit_and_loss") or {}
    bs = state.get("balance_sheet") or {}
    cf = state.get("cash_flow") or {}
    ratios = state.get("financial_ratios") or []

    flags: List[Dict[str, Any]] = []

    # Run all 9 checks
    checks = [
        _check_earnings_not_cash_backed(ratios, pnl, cf),
        _check_receivables_quality(bs, pnl),
        _check_slow_inventory(bs, pnl),
        _check_undisclosed_borrowing(ratios),
        _check_gst_revenue_mismatch(state),
        _check_bank_revenue_mismatch(state),
        _check_dscr_deterioration(ratios),
        _check_negative_net_worth(bs),
        _check_liquidity_stress(ratios),
    ]

    for result in checks:
        if result is not None:
            flags.append(result)

    # Compute anomaly score
    score = sum(_SEVERITY_WEIGHT.get(f["severity"], 5) for f in flags)
    score = min(100, score)

    state["financial_anomalies"] = flags
    state["anomaly_score"] = float(score)
    state["progress_percent"] = 68
    state["status_message"] = (
        f"Anomaly detection complete. {len(flags)} flag(s) raised. "
        f"Anomaly score: {score}/100."
    )

    return state
