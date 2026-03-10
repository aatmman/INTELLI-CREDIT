"""
Research: Sector Research Node — Tavily search for sector outlook + regulation.

3 queries for RBI regulation, industry outlook, and SEBI/RBI circulars.
"""

import re
from datetime import datetime
from typing import Any, Dict, List
from agents.state import CreditApplicationState
from services.tavily_service import get_tavily_client


# ---------------------------------------------------------------------------
# Severity scoring
# ---------------------------------------------------------------------------

_SEVERITY_RULES = [
    (r"(?:restriction|ban|moratorium|RBI\s*(?:curb|restrict)|lending\s*cap)", "high", 12),
    (r"(?:stress|headwind|slowdown|downturn|contraction|NPA\s*ris)", "medium", 7),
    (r"(?:growth|expansion|positive\s*outlook|tailwind|boom|recovery)", "low", 0),
]


def _score_finding(title: str, content: str) -> tuple:
    combined = f"{title} {content}".lower()
    for pattern, severity, impact in _SEVERITY_RULES:
        if re.search(pattern, combined, re.IGNORECASE):
            return severity, impact
    return "low", 2


def _make_finding(result: Dict) -> Dict[str, Any]:
    title = result.get("title", "")
    content = result.get("content", "")
    severity, risk_impact = _score_finding(title, content)
    published = result.get("published_date", "") or datetime.utcnow().strftime("%Y-%m-%d")
    if len(published) > 10:
        published = published[:10]

    return {
        "source_type": "sector",
        "title": title[:200],
        "summary": content[:300] if content else title,
        "url": result.get("url", ""),
        "published_date": published,
        "severity": severity,
        "risk_impact": risk_impact,
        "reviewed_by_analyst": False,
    }


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def sector_research_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    Search for sector-level risks, regulation, and outlook.
    3 Tavily queries, deduped by URL.
    """
    state["current_node"] = "sector_research"
    state["status_message"] = "Researching sector outlook..."

    sector = state.get("sector", "")
    if not sector:
        state["sector_research"] = []
        return state

    queries = [
        f"{sector} India RBI regulation 2024 2025 credit risk",
        f"{sector} India industry outlook headwinds tailwinds 2025",
        f"{sector} SEBI RBI circular restriction India 2025",
    ]

    all_findings: List[Dict[str, Any]] = []
    seen_urls = set()
    client = get_tavily_client()

    for query in queries:
        try:
            result = client.search(query=query, max_results=5, search_depth="advanced")
            for r in result.get("results", []):
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_findings.append(_make_finding(r))
        except Exception as exc:
            print(f"[SectorResearch] Query failed: {exc}")

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 4))

    state["sector_research"] = all_findings
    state["status_message"] = f"Sector research complete. {len(all_findings)} findings."

    return state
