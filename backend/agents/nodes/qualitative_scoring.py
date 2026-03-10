"""
Agent 3: Qualitative Scoring Node — Field visit → risk adjustments.

Reads field visit data from `field_visit_notes` table.
Maps observations to risk score adjustments per PRD:
  - Capacity utilization → -20 to +5
  - Factory condition → -15 to +10
  - Management transparency → -5 to +10 (risk)
  - Inventory verified → -5 to +12
  - Workers present → flag if <10 for manufacturing

Uses Groq API to generate natural language field visit summary.
Updates state with qualitative_risk_adjustment, field_visit_summary,
and management_quality_score.
"""

import json
from typing import Any, Dict, List, Optional
from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Scoring rules from PRD
# ---------------------------------------------------------------------------

def _score_capacity_utilization(pct: Optional[float]) -> Dict[str, Any]:
    """Capacity utilization scoring per PRD."""
    if pct is None:
        return {"parameter": "capacity_utilization", "adjustment": 0, "note": "Not assessed"}
    if pct < 30:
        return {"parameter": "capacity_utilization", "adjustment": -20, "note": f"Very low ({pct:.0f}%)"}
    elif pct < 50:
        return {"parameter": "capacity_utilization", "adjustment": -12, "note": f"Below average ({pct:.0f}%)"}
    elif pct < 75:
        return {"parameter": "capacity_utilization", "adjustment": -5, "note": f"Moderate ({pct:.0f}%)"}
    else:
        return {"parameter": "capacity_utilization", "adjustment": 5, "note": f"Good ({pct:.0f}%)"}


def _score_factory_condition(condition: Optional[str]) -> Dict[str, Any]:
    """Factory condition scoring per PRD."""
    if not condition:
        return {"parameter": "factory_condition", "adjustment": 0, "note": "Not assessed"}
    c = condition.strip().lower()
    mapping = {"poor": -15, "average": -5, "good": 5, "excellent": 10}
    adj = mapping.get(c, 0)
    return {"parameter": "factory_condition", "adjustment": adj, "note": f"{condition} condition"}


def _score_management_transparency(transparency: Optional[str]) -> Dict[str, Any]:
    """Management transparency scoring per PRD (positive = risk increase)."""
    if not transparency:
        return {"parameter": "management_transparency", "adjustment": 0, "note": "Not assessed"}
    t = transparency.strip().lower()
    # These are RISK additions: evasive=+10 risk, cooperative=-5 risk
    mapping = {"evasive": 10, "partial": 5, "cooperative": -5, "transparent": -5}
    adj = mapping.get(t, 0)
    return {"parameter": "management_transparency", "adjustment": adj, "note": f"Management {transparency}"}


def _score_inventory_verification(result: Optional[str]) -> Dict[str, Any]:
    """Inventory verification scoring per PRD."""
    if not result:
        return {"parameter": "inventory_verified", "adjustment": 0, "note": "Not verified"}
    r = result.strip().lower()
    if r in ("discrepancy", "mismatch", "does not match", "no"):
        return {"parameter": "inventory_verified", "adjustment": 12, "note": "Inventory discrepancy found"}
    elif r in ("matches", "match", "yes", "verified", "ok"):
        return {"parameter": "inventory_verified", "adjustment": -5, "note": "Inventory matches records"}
    return {"parameter": "inventory_verified", "adjustment": 0, "note": f"Result: {result}"}


def _check_workers(workers: Optional[int], sector: str) -> Optional[Dict[str, Any]]:
    """Flag if <10 workers for manufacturing."""
    if workers is None:
        return None
    manufacturing_sectors = (
        "manufacturing", "textile", "steel", "chemical", "pharma",
        "auto", "engineering", "food processing", "fmcg",
    )
    is_manufacturing = any(s in sector.lower() for s in manufacturing_sectors)
    if is_manufacturing and workers < 10:
        return {
            "parameter": "workers_present",
            "adjustment": 8,
            "note": f"Only {workers} workers present for manufacturing unit — suspicious",
        }
    return None


# ---------------------------------------------------------------------------
# DB + Groq helpers
# ---------------------------------------------------------------------------

def _fetch_field_visit(application_id: str) -> Optional[Dict[str, Any]]:
    """Fetch field visit notes from field_visit_notes table."""
    try:
        supabase = get_supabase()
        result = supabase.table("field_visit_notes").select("*").eq(
            "application_id", application_id
        ).order("created_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]
    except Exception as exc:
        print(f"[QualitativeScoring] Failed to fetch field visit: {exc}")
    return None


async def _generate_groq_summary(field_data: Dict) -> str:
    """Use Groq to generate natural language field visit summary."""
    try:
        from services.groq_service import groq_chat_completion
        prompt = (
            "Summarize this field visit for a credit appraisal memo in 3 sentences. "
            f"Observations: {json.dumps(field_data, default=str)}. "
            "Focus on operational health and risk signals."
        )
        summary = await groq_chat_completion(
            messages=[
                {"role": "system", "content": "You are an Indian banking credit analyst writing concise field visit summaries."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        return summary.strip()
    except Exception as exc:
        print(f"[QualitativeScoring] Groq summary failed: {exc}")
        return "Field visit summary unavailable — Groq API error."


def _compute_management_quality(adjustments: List[Dict]) -> float:
    """Convert adjustments to a 0–100 management quality score."""
    # Start at 60 (baseline), adjust
    score = 60.0
    for adj in adjustments:
        # Negative adjustments = bad → decrease score
        # Positive adjustments (risk items) = bad → also decrease score
        param = adj["parameter"]
        val = adj["adjustment"]
        if param == "management_transparency":
            # For transparency: positive means more risk
            score -= val * 2
        else:
            # For others: positive means positive, negative means bad
            score += val
    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def qualitative_scoring_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Qualitative Scoring.

    1. Fetch field visit data from field_visit_notes table
    2. Map observations to risk score adjustments per PRD
    3. Generate NL summary using Groq
    4. Update state with adjustments, summary, and management score
    """
    state["current_node"] = "qualitative_scoring"
    state["progress_percent"] = 40
    state["status_message"] = "Processing field visit observations..."

    errors: list = list(state.get("errors") or [])
    warnings: list = list(state.get("warnings") or [])
    application_id = state.get("application_id", "")
    sector = state.get("sector", "")

    # ── Fetch field visit data ──
    field_visit = _fetch_field_visit(application_id)

    if not field_visit:
        warnings.append("[qualitative_scoring] No field visit notes found")
        state["warnings"] = warnings
        state["qualitative_risk_adjustments"] = []
        state["qualitative_score"] = 0.0
        state["status_message"] = "No field visit data available."
        state["progress_percent"] = 45
        return state

    # Store raw structured data
    state["field_visit_structured"] = field_visit
    state["field_visit_notes"] = field_visit.get("observations", "")

    # ── Parse observations ──
    observations = field_visit.get("observations") or {}
    if isinstance(observations, str):
        # Try JSON parse
        try:
            observations = json.loads(observations)
        except (json.JSONDecodeError, TypeError):
            observations = {"raw_notes": observations}

    # ── Apply scoring rules ──
    adjustments: List[Dict[str, Any]] = []

    # 1. Capacity utilization
    capacity = observations.get("capacity_utilization")
    if capacity is not None:
        try:
            capacity = float(str(capacity).replace("%", ""))
        except (ValueError, TypeError):
            capacity = None
    adjustments.append(_score_capacity_utilization(capacity))

    # 2. Factory condition
    adjustments.append(_score_factory_condition(
        observations.get("factory_condition") or observations.get("premise_condition")
    ))

    # 3. Management transparency
    adjustments.append(_score_management_transparency(
        observations.get("management_transparency") or observations.get("management_cooperation")
    ))

    # 4. Inventory verification
    adjustments.append(_score_inventory_verification(
        observations.get("inventory_verified") or observations.get("inventory_match")
    ))

    # 5. Workers check
    workers = observations.get("workers_present") or observations.get("employees_present")
    if workers is not None:
        try:
            workers = int(workers)
        except (ValueError, TypeError):
            workers = None
    worker_flag = _check_workers(workers, sector)
    if worker_flag:
        adjustments.append(worker_flag)

    # ── Compute total risk adjustment ──
    total_adjustment = sum(a["adjustment"] for a in adjustments)
    state["qualitative_risk_adjustments"] = adjustments
    state["qualitative_score"] = float(total_adjustment)

    # ── Management quality score ──
    mgmt_score = _compute_management_quality(adjustments)
    # Store as part of field_visit_structured for downstream
    state["field_visit_structured"]["management_quality_score"] = mgmt_score

    # ── Generate Groq summary ──
    state["status_message"] = "Generating field visit summary with AI..."
    summary = await _generate_groq_summary(field_visit)
    state["field_visit_structured"]["ai_summary"] = summary

    state["errors"] = errors
    state["warnings"] = warnings
    state["progress_percent"] = 48
    state["status_message"] = (
        f"Qualitative scoring complete. "
        f"Risk adjustment: {total_adjustment:+d} points. "
        f"Management quality: {mgmt_score:.0f}/100."
    )

    return state
