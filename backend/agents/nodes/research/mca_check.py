"""
Research: MCA Check Node — Tavily search for MCA21 filings, charges, disqualifications.

3 queries for charge registration, director disqualification, struck off status.
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
    (r"(?:struck\s*off|under\s*liquidation|winding\s*up|dissolved)", "critical", 30),
    (r"(?:director\s*disqualif)", "high", 15),
    (r"(?:new\s*charge|charge\s*created|charge\s*registered)", "medium", 8),
    (r"(?:annual\s*return\s*(?:filing\s*)?default|non[- ]?filing|overdue)", "medium", 6),
    (r"(?:ROC\s*notice|show\s*cause|compounding\s*of\s*offence)", "medium", 7),
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
        "source_type": "mca",
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

async def mca_check_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    Search MCA21 for charges, director disqualification, struck off status.
    3 Tavily queries, deduped by URL.
    """
    state["current_node"] = "mca_check"
    state["status_message"] = "Checking MCA21 filings..."

    company_name = state.get("company_name", "")
    cin = state.get("cin_number", "")

    if not company_name:
        state["mca_findings"] = []
        return state

    queries = [
        f"{company_name} MCA21 charge registration site:mca.gov.in OR new charge created",
        f"{company_name} CIN {cin} director disqualification MCA" if cin else f"{company_name} director disqualification MCA India",
        f"{company_name} annual return filing MCA struck off",
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
            print(f"[MCACheck] Query failed: {exc}")

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 4))

    state["mca_findings"] = all_findings
    state["status_message"] = f"MCA check complete. {len(all_findings)} findings."

    return state
