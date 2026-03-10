"""
Agent 5: Risk Timeline Builder — Chronological red flag aggregation.

THIS IS THE PRD DIFFERENTIATOR — no other team builds this.

Aggregates ALL red flags from ALL sources chronologically:
  - anomaly_flags → source: financial
  - gst_flags → source: gst
  - banking_flags → source: banking
  - research_findings table → source: news / mca / ecourts / rbi
  - Field visit risk flags → source: field_visit
  - Policy rule FAILs → source: policy

Each event: date, source, severity, title, description, risk_impact, source_url
Sorted chronologically. Color-coded by severity in downstream UI.
Updates state with timeline_events and timeline_risk_score.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Severity → risk impact weight
# ---------------------------------------------------------------------------

_SEVERITY_IMPACT = {
    "critical": 30.0,
    "high": 20.0,
    "medium": 10.0,
    "low": 5.0,
}


# ---------------------------------------------------------------------------
# Source collectors
# ---------------------------------------------------------------------------

def _collect_financial_anomalies(state: CreditApplicationState) -> List[Dict[str, Any]]:
    """Pull anomaly_flags from state → source: financial."""
    events = []
    anomalies = state.get("financial_anomalies") or []
    # Use latest financial year end as approximate date
    now = datetime.utcnow()
    # Approximate: FY end = March 31 of current or previous year
    fy_end = datetime(now.year, 3, 31) if now.month > 3 else datetime(now.year - 1, 3, 31)

    for i, flag in enumerate(anomalies):
        events.append({
            "date": fy_end.strftime("%Y-%m-%d"),
            "source": "financial",
            "severity": flag.get("severity", "medium"),
            "title": flag.get("flag_type", "Unknown anomaly"),
            "description": flag.get("description", ""),
            "risk_impact": _SEVERITY_IMPACT.get(flag.get("severity", "medium"), 10.0),
            "source_url": None,
        })
    return events


def _collect_gst_flags(state: CreditApplicationState) -> List[Dict[str, Any]]:
    """Pull gst_flags from state → source: gst."""
    events = []
    flags = state.get("gst_flags") or []
    now = datetime.utcnow()

    for flag in flags:
        # Try to extract month from flag data
        month_str = flag.get("month") or flag.get("period")
        if month_str:
            event_date = month_str  # Already formatted
        else:
            event_date = now.strftime("%Y-%m-%d")

        events.append({
            "date": event_date,
            "source": "gst",
            "severity": flag.get("severity", "medium"),
            "title": flag.get("flag", flag.get("flag_type", "GST flag")),
            "description": flag.get("detail", flag.get("description", "")),
            "risk_impact": float(flag.get("risk_points", _SEVERITY_IMPACT.get(flag.get("severity", "medium"), 10.0))),
            "source_url": None,
        })
    return events


def _collect_banking_flags(state: CreditApplicationState) -> List[Dict[str, Any]]:
    """Pull banking_flags from state → source: banking."""
    events = []
    flags = state.get("banking_flags") or []
    now = datetime.utcnow()

    for flag in flags:
        month_str = flag.get("month") or flag.get("period")
        event_date = month_str if month_str else now.strftime("%Y-%m-%d")

        events.append({
            "date": event_date,
            "source": "banking",
            "severity": flag.get("severity", "medium"),
            "title": flag.get("flag", flag.get("flag_type", "Banking flag")),
            "description": flag.get("detail", flag.get("description", "")),
            "risk_impact": float(flag.get("risk_points", _SEVERITY_IMPACT.get(flag.get("severity", "medium"), 10.0))),
            "source_url": None,
        })
    return events


def _collect_research_findings(application_id: str) -> List[Dict[str, Any]]:
    """Pull from research_findings table in Supabase → source: news/mca/ecourts/rbi."""
    events = []
    try:
        supabase = get_supabase()
        result = supabase.table("research_findings").select("*").eq(
            "application_id", application_id
        ).execute()
        findings = result.data or []
    except Exception as exc:
        print(f"[RiskTimeline] Failed to fetch research: {exc}")
        findings = []

    # Also check state for research findings
    for finding in findings:
        source_type = finding.get("source", "news")
        source_map = {
            "tavily": "news",
            "mca": "mca",
            "ecourts": "ecourts",
            "rbi": "rbi",
            "sector_news": "news",
        }

        events.append({
            "date": finding.get("published_date") or finding.get("created_at", "")[:10],
            "source": source_map.get(source_type, source_type),
            "severity": finding.get("severity", "medium"),
            "title": finding.get("title", "Research finding"),
            "description": finding.get("summary", ""),
            "risk_impact": float(finding.get("risk_points") or _SEVERITY_IMPACT.get(finding.get("severity", "medium"), 10.0)),
            "source_url": finding.get("url"),
        })
    return events


def _collect_research_from_state(state: CreditApplicationState) -> List[Dict[str, Any]]:
    """Pull research findings directly from state (if populated by research nodes)."""
    events = []
    all_findings = state.get("all_research_findings") or []

    for finding in all_findings:
        source_type = finding.get("source", "news")
        events.append({
            "date": finding.get("published_date", ""),
            "source": source_type,
            "severity": finding.get("severity", "medium"),
            "title": finding.get("title", "Research finding"),
            "description": finding.get("summary", ""),
            "risk_impact": float(finding.get("risk_points") or _SEVERITY_IMPACT.get(finding.get("severity", "medium"), 10.0)),
            "source_url": finding.get("url"),
        })
    return events


def _collect_field_visit_flags(state: CreditApplicationState) -> List[Dict[str, Any]]:
    """Pull field visit risk flags → source: field_visit."""
    events = []
    adjustments = state.get("qualitative_risk_adjustments") or []

    for adj in adjustments:
        # Only include negative adjustments as events
        if adj.get("adjustment", 0) >= 5:  # Risk items (positive = more risk)
            visit_data = state.get("field_visit_structured") or {}
            visit_date = visit_data.get("visit_date") or visit_data.get("created_at", "")
            if visit_date and len(visit_date) > 10:
                visit_date = visit_date[:10]

            events.append({
                "date": visit_date or datetime.utcnow().strftime("%Y-%m-%d"),
                "source": "field_visit",
                "severity": "high" if adj["adjustment"] >= 10 else "medium",
                "title": f"Field visit: {adj['parameter']}",
                "description": adj.get("note", ""),
                "risk_impact": float(abs(adj["adjustment"])),
                "source_url": None,
            })
    return events


def _collect_policy_fails(state: CreditApplicationState) -> List[Dict[str, Any]]:
    """Pull policy rule FAILs → source: policy."""
    events = []
    policy_results = state.get("policy_check_results") or []

    for result in policy_results:
        if result.get("result") == "FAIL":
            events.append({
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "source": "policy",
                "severity": "critical" if result.get("rule_type") == "hard" else "high",
                "title": f"Policy: {result.get('rule_name', 'Unknown')}",
                "description": (
                    f"{result.get('parameter', '?')} {result.get('operator', '?')} "
                    f"{result.get('threshold', '?')} (actual: {result.get('actual_value', 'N/A')})"
                ),
                "risk_impact": 25.0 if result.get("rule_type") == "hard" else 15.0,
                "source_url": None,
            })
    return events


# ---------------------------------------------------------------------------
# Timeline scoring
# ---------------------------------------------------------------------------

def _compute_timeline_risk_score(events: List[Dict[str, Any]]) -> float:
    """
    Compute aggregate risk score from timeline events.

    Weighted by recency: events in last 3 months get full weight,
    3-12 months get 0.7×, older get 0.4×.
    Capped at 100.
    """
    now = datetime.utcnow()
    score = 0.0

    for event in events:
        impact = event.get("risk_impact", 10.0)

        # Parse date for recency weighting
        date_str = event.get("date", "")
        try:
            if len(date_str) == 10:
                event_date = datetime.strptime(date_str, "%Y-%m-%d")
            elif len(date_str) > 10:
                event_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            else:
                event_date = now  # Unknown date → full weight
        except (ValueError, TypeError):
            event_date = now

        days_ago = (now - event_date).days
        if days_ago <= 90:
            weight = 1.0
        elif days_ago <= 365:
            weight = 0.7
        else:
            weight = 0.4

        score += impact * weight

    return min(100.0, round(score, 2))


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def risk_timeline_builder_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Risk Timeline Builder (DIFFERENTIATOR).

    Aggregates ALL red flags from ALL sources chronologically.
    Each event has: date, source, severity, title, description, risk_impact, source_url.
    Sorted by date. Scored with recency weighting.
    """
    state["current_node"] = "risk_timeline"
    state["progress_percent"] = 70
    state["status_message"] = "Building risk timeline..."

    application_id = state.get("application_id", "")

    # ── Collect from all sources ──
    all_events: List[Dict[str, Any]] = []

    all_events.extend(_collect_financial_anomalies(state))
    all_events.extend(_collect_gst_flags(state))
    all_events.extend(_collect_banking_flags(state))

    # Research: from DB + from state
    if application_id:
        all_events.extend(_collect_research_findings(application_id))
    all_events.extend(_collect_research_from_state(state))

    all_events.extend(_collect_field_visit_flags(state))
    all_events.extend(_collect_policy_fails(state))

    # ── Deduplicate by title+source ──
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for event in all_events:
        key = (event.get("title", ""), event.get("source", ""), event.get("date", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(event)

    # ── Sort chronologically ──
    def _sort_key(e: Dict) -> str:
        d = e.get("date", "")
        if not d:
            return "9999-99-99"
        return d[:10]

    deduped.sort(key=_sort_key)

    # ── Compute risk score ──
    risk_score = _compute_timeline_risk_score(deduped)

    # ── Source breakdown ──
    source_counts: Dict[str, int] = {}
    for event in deduped:
        src = event.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    # ── Update state ──
    state["timeline_events"] = deduped
    state["timeline_risk_score"] = risk_score
    state["progress_percent"] = 75
    state["status_message"] = (
        f"Risk timeline built. {len(deduped)} events across "
        f"{len(source_counts)} sources. Timeline risk score: {risk_score:.1f}/100."
    )

    return state
