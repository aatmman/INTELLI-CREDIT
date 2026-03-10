"""
Research: Aggregator Node — Collects, deduplicates, scores, and stores
all research findings from the 5 parallel research nodes.

Performs:
  1. Deduplication (same company+topic → keep highest severity, merge URLs)
  2. Total external risk score (sum of risk_impact, capped at 100)
  3. Research summary for CAM (top 5 findings formatted as bullets)
  4. Store ALL findings in research_findings Supabase table
  5. Update CreditApplicationState
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Severity ordering for dedup tiebreaking
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_LABELS = ["critical", "high", "medium", "low"]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Normalize title for dedup comparison."""
    import re
    return re.sub(r"[^a-z0-9]", "", title.lower())[:80]


def _deduplicate(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate findings by normalized title.
    If same topic appears >1 time, keep highest severity, merge URLs.
    """
    seen: Dict[str, Dict[str, Any]] = {}

    for finding in findings:
        key = _normalize_title(finding.get("title", ""))
        if not key:
            # No title → can't dedup, keep as-is
            seen[f"_notitle_{len(seen)}"] = finding
            continue

        existing = seen.get(key)
        if not existing:
            seen[key] = finding
        else:
            # Keep higher severity
            existing_rank = _SEVERITY_ORDER.get(existing["severity"], 4)
            new_rank = _SEVERITY_ORDER.get(finding["severity"], 4)
            if new_rank < existing_rank:
                # New finding is more severe — replace but merge URL
                old_url = existing.get("url", "")
                finding["merged_urls"] = list(set(
                    existing.get("merged_urls", [old_url]) + [finding.get("url", "")]
                ))
                seen[key] = finding
            else:
                # Existing is more severe — just merge URL
                existing.setdefault("merged_urls", [existing.get("url", "")])
                new_url = finding.get("url", "")
                if new_url and new_url not in existing["merged_urls"]:
                    existing["merged_urls"].append(new_url)

    return list(seen.values())


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_external_risk_score(findings: List[Dict[str, Any]]) -> float:
    """Sum all risk_impact values, capped at 100."""
    total = sum(float(f.get("risk_impact", 0)) for f in findings)
    return min(100.0, round(total, 2))


# ---------------------------------------------------------------------------
# Summary for CAM
# ---------------------------------------------------------------------------

def _build_research_summary(findings: List[Dict[str, Any]]) -> str:
    """Top 5 findings by severity, formatted as bullet points for CAM."""
    # Sort by severity (critical first), then by risk_impact
    sorted_findings = sorted(
        findings,
        key=lambda f: (
            _SEVERITY_ORDER.get(f.get("severity", "low"), 4),
            -float(f.get("risk_impact", 0)),
        ),
    )

    top5 = sorted_findings[:5]
    if not top5:
        return "No significant external risk signals found."

    lines = ["Top Research Findings:"]
    for i, f in enumerate(top5, 1):
        severity = f.get("severity", "low").upper()
        source = f.get("source_type", "unknown")
        title = f.get("title", "Unknown")[:100]
        impact = f.get("risk_impact", 0)
        lines.append(
            f"  {i}. [{severity}] ({source}) {title} — risk impact: {impact} pts"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Supabase storage
# ---------------------------------------------------------------------------

def _store_findings(application_id: str, findings: List[Dict[str, Any]]) -> None:
    """Store all findings in research_findings table."""
    if not findings:
        return
    try:
        supabase = get_supabase()
        rows = []
        for f in findings:
            rows.append({
                "application_id": application_id,
                "source": f.get("source_type", "unknown"),
                "title": f.get("title", "")[:200],
                "summary": f.get("summary", "")[:500],
                "url": f.get("url", ""),
                "published_date": f.get("published_date"),
                "severity": f.get("severity", "low"),
                "risk_points": float(f.get("risk_impact", 0)),
                "reviewed_by_analyst": False,
                "created_at": datetime.utcnow().isoformat(),
            })
        supabase.table("research_findings").insert(rows).execute()
        print(f"[ResearchAggregator] ✓ Stored {len(rows)} findings")
    except Exception as exc:
        print(f"[ResearchAggregator] ✗ DB insert failed: {exc}")


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def research_aggregator_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — Research Aggregator.

    Collects ALL findings from the 5 parallel research nodes,
    deduplicates, scores, stores to DB, and updates state.
    """
    state["current_node"] = "research_aggregator"
    state["progress_percent"] = 58
    state["status_message"] = "Aggregating research findings..."

    application_id = state.get("application_id", "")

    # ── Collect from all 5 research node outputs ──
    all_findings: List[Dict[str, Any]] = []

    all_findings.extend(state.get("company_news") or [])
    all_findings.extend(state.get("mca_findings") or [])
    all_findings.extend(state.get("ecourts_findings") or [])
    all_findings.extend(state.get("sector_research") or [])
    all_findings.extend(state.get("rbi_list_findings") or [])

    if not all_findings:
        state["all_research_findings"] = []
        state["research_risk_score"] = 0.0
        state["status_message"] = "No research findings to aggregate."
        state["progress_percent"] = 62
        return state

    # ── Deduplicate ──
    deduped = _deduplicate(all_findings)

    # ── Score ──
    risk_score = _compute_external_risk_score(deduped)

    # ── Build CAM summary ──
    summary = _build_research_summary(deduped)

    # ── Store to Supabase ──
    if application_id:
        _store_findings(application_id, deduped)

    # ── Source breakdown ──
    source_counts: Dict[str, int] = {}
    for f in deduped:
        src = f.get("source_type", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    severity_counts: Dict[str, int] = {}
    for f in deduped:
        sev = f.get("severity", "low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # ── Update state ──
    state["all_research_findings"] = deduped
    state["research_risk_score"] = risk_score

    state["progress_percent"] = 62
    state["status_message"] = (
        f"Research complete. {len(deduped)} findings "
        f"({severity_counts.get('critical', 0)} critical, "
        f"{severity_counts.get('high', 0)} high, "
        f"{severity_counts.get('medium', 0)} medium, "
        f"{severity_counts.get('low', 0)} low). "
        f"External risk score: {risk_score:.0f}/100."
    )

    return state
