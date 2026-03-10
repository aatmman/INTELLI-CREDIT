"""
Agent 7: Policy Guard Node — Dynamic credit policy rules engine.

Fetches all active rules from `policy_rules` table in Supabase (never hardcoded).
Evaluates each rule against CreditApplicationState using configurable operators.
Hard-rule FAILs require analyst justification to proceed.

Supports operators: >=, <=, >, <, ==, !=
Supports sector-specific rules via sector_specific column.

Updates state with policy_results, policy_exceptions, policy_exception_required.
"""

import operator
from typing import Any, Dict, List, Optional
from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Operator mapping
# ---------------------------------------------------------------------------

_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_policy_rules(sector: str = "") -> List[Dict[str, Any]]:
    """Fetch active policy rules from policy_rules table."""
    try:
        supabase = get_supabase()
        query = supabase.table("policy_rules").select("*").eq("is_active", True)
        result = query.execute()
        rules = result.data or []

        # Filter sector-specific rules
        filtered = []
        for rule in rules:
            rule_sector = rule.get("sector_specific", "")
            if not rule_sector or rule_sector.lower() == "all":
                filtered.append(rule)
            elif sector and rule_sector.lower() == sector.lower():
                filtered.append(rule)
        return filtered
    except Exception as exc:
        print(f"[PolicyCheck] Failed to fetch rules: {exc}")
        return []


# ---------------------------------------------------------------------------
# Parameter extraction from state
# ---------------------------------------------------------------------------

def _extract_param_value(state: CreditApplicationState, parameter: str) -> Optional[float]:
    """
    Extract a parameter value from state.
    Supports dotted paths like 'balance_sheet.net_worth' and
    flat keys like 'dscr', 'current_ratio', 'anomaly_score'.
    """
    # Flat state keys
    if parameter in state:
        val = state.get(parameter)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

    # Dotted path: e.g. 'balance_sheet.net_worth'
    parts = parameter.split(".")
    current: Any = state
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None

    try:
        return float(current)
    except (ValueError, TypeError):
        return None

    # Check in latest financial ratios
    ratios = state.get("financial_ratios") or []
    if ratios:
        latest = ratios[-1]
        val = latest.get(parameter)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass

    return None


def _resolve_parameter(state: CreditApplicationState, parameter: str) -> Optional[float]:
    """
    Try multiple strategies to find the parameter value.
    
    Common parameters: dscr, current_ratio, debt_equity_ratio, net_worth,
    interest_coverage, pat_margin, total_revenue, anomaly_score, etc.
    """
    # 1. Direct state key
    val = _extract_param_value(state, parameter)
    if val is not None:
        return val

    # 2. From financial_ratios (latest year)
    ratios = state.get("financial_ratios") or []
    if ratios:
        latest = ratios[-1] if isinstance(ratios[-1], dict) else {}
        ratio_val = latest.get(parameter)
        if ratio_val is not None:
            try:
                return float(ratio_val)
            except (ValueError, TypeError):
                pass

    # 3. From balance_sheet
    bs = state.get("balance_sheet") or {}
    if parameter in bs:
        try:
            return float(bs[parameter])
        except (ValueError, TypeError):
            pass

    # 4. From profit_and_loss
    pnl = state.get("profit_and_loss") or {}
    if parameter in pnl:
        try:
            return float(pnl[parameter])
        except (ValueError, TypeError):
            pass

    # 5. Common aliases
    aliases = {
        "net_worth": ["shareholders_funds", "total_equity"],
        "dscr": ["debt_service_coverage_ratio"],
        "current_ratio": ["cr"],
        "debt_equity_ratio": ["de_ratio", "debt_equity"],
        "interest_coverage": ["icr", "interest_coverage_ratio"],
        "pat_margin": ["net_profit_margin"],
    }
    for alias in aliases.get(parameter, []):
        val = _extract_param_value(state, alias)
        if val is not None:
            return val

    return None


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------

def _evaluate_rule(
    state: CreditApplicationState,
    rule: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate a single policy rule against state.

    Returns: {rule_name, rule_type, result, actual_value, threshold, deviation}
    """
    rule_name = rule.get("rule_name", "Unknown")
    rule_type = rule.get("rule_type", "soft")  # hard or soft
    parameter = rule.get("parameter", "")
    op_str = rule.get("operator", ">=")
    threshold = rule.get("threshold")
    risk_impact = rule.get("risk_impact", "")

    result_entry = {
        "rule_name": rule_name,
        "rule_type": rule_type,
        "parameter": parameter,
        "operator": op_str,
        "threshold": threshold,
        "risk_impact": risk_impact,
        "actual_value": None,
        "result": "DATA_UNAVAILABLE",
        "deviation": None,
    }

    # Get threshold as float
    try:
        threshold_val = float(threshold) if threshold is not None else None
    except (ValueError, TypeError):
        threshold_val = None

    if threshold_val is None:
        return result_entry

    # Get actual value
    actual = _resolve_parameter(state, parameter)
    result_entry["actual_value"] = actual

    if actual is None:
        return result_entry

    # Get operator function
    op_func = _OPERATORS.get(op_str)
    if not op_func:
        result_entry["result"] = "INVALID_OPERATOR"
        return result_entry

    # Evaluate
    passed = op_func(actual, threshold_val)
    result_entry["result"] = "PASS" if passed else "FAIL"

    # Compute deviation
    if threshold_val != 0:
        result_entry["deviation"] = round(
            ((actual - threshold_val) / abs(threshold_val)) * 100, 2
        )
    else:
        result_entry["deviation"] = 0.0

    return result_entry


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def policy_check_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Policy Check.

    1. Fetch all active rules from policy_rules table
    2. Evaluate each rule against CreditApplicationState
    3. Hard rule FAIL → policy_exception_required = True
    4. Update state with results and exceptions
    """
    state["current_node"] = "policy_check"
    state["progress_percent"] = 80
    state["status_message"] = "Running policy compliance checks..."

    errors: list = list(state.get("errors") or [])
    warnings: list = list(state.get("warnings") or [])
    sector = state.get("sector", "")

    # ── Fetch rules from DB ──
    rules = _fetch_policy_rules(sector)

    if not rules:
        warnings.append("[policy_check] No active policy rules found in DB")
        state["warnings"] = warnings
        state["policy_check_results"] = []
        state["policy_exceptions"] = []
        state["policy_overall_status"] = "no_rules"
        state["progress_percent"] = 82
        state["status_message"] = "No policy rules to check."
        return state

    # ── Evaluate all rules ──
    results: List[Dict[str, Any]] = []
    exceptions: List[str] = []
    hard_fail = False

    for rule in rules:
        result = _evaluate_rule(state, rule)
        results.append(result)

        if result["result"] == "FAIL":
            if result["rule_type"] == "hard":
                hard_fail = True
                exceptions.append(
                    f"HARD RULE VIOLATION: {result['rule_name']} — "
                    f"{result['parameter']} {result['operator']} {result['threshold']} "
                    f"(actual: {result['actual_value']}, "
                    f"deviation: {result['deviation']}%)"
                )
            elif result["rule_type"] == "soft":
                warnings.append(
                    f"Soft policy warning: {result['rule_name']} — "
                    f"{result['parameter']} {result['operator']} {result['threshold']} "
                    f"(actual: {result['actual_value']})"
                )

    # ── Summary ──
    total = len(results)
    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = sum(1 for r in results if r["result"] == "FAIL")
    unavailable = sum(1 for r in results if r["result"] == "DATA_UNAVAILABLE")

    state["policy_check_results"] = results
    state["policy_exceptions"] = exceptions
    state["policy_overall_status"] = "exception_required" if hard_fail else "compliant"
    state["errors"] = errors
    state["warnings"] = warnings
    state["progress_percent"] = 85
    state["status_message"] = (
        f"Policy check complete. {passed}/{total} passed, "
        f"{failed} failed, {unavailable} data unavailable. "
        f"{'Exception required.' if hard_fail else 'Compliant.'}"
    )

    return state
