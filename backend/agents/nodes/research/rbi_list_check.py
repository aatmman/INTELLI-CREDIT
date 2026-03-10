"""
Research: RBI List Check Node — Tavily search for defaulter/caution lists.

3 queries for wilful defaulter, RBI caution list, and CIBIL default.
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
    (r"(?:wilful\s*default(?:er)?|willful\s*default)", "critical", 30),
    (r"(?:RBI\s*caution\s*list|caution\s*advis(?:ed|ory)|specific\s*approval)", "critical", 28),
    (r"(?:CIBIL\s*default|credit\s*score\s*(?:low|poor)|SMA[- ]2|NPA)", "high", 20),
    (r"(?:overdue|SMA[- ]1|restructured)", "medium", 10),
]


def _score_finding(title: str, content: str) -> tuple:
    combined = f"{title} {content}".lower()
    for pattern, severity, impact in _SEVERITY_RULES:
        if re.search(pattern, combined, re.IGNORECASE):
            return severity, impact
    return "low", 3


def _make_finding(result: Dict) -> Dict[str, Any]:
    title = result.get("title", "")
    content = result.get("content", "")
    severity, risk_impact = _score_finding(title, content)
    published = result.get("published_date", "") or datetime.utcnow().strftime("%Y-%m-%d")
    if len(published) > 10:
        published = published[:10]

    return {
        "source_type": "rbi",
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

async def rbi_list_check_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    Check RBI defaulter/caution lists and CIBIL defaults.
    3 Tavily queries, deduped by URL.
    """
    state["current_node"] = "rbi_list_check"
    state["status_message"] = "Checking RBI defaulter lists..."

    company_name = state.get("company_name", "")
    if not company_name:
        state["rbi_list_findings"] = []
        return state

    # Get promoter name
    promoter_name = ""
    kyc_data = state.get("kyc_data") or []
    for kyc in kyc_data:
        directors = (kyc.get("extracted_data") or {}).get("directors") or []
        if directors:
            promoter_name = directors[0].get("name", "")
            break

    queries = [
        f"{company_name} RBI defaulter list caution list India",
        f"{promoter_name} RBI wilful defaulter CIBIL NPA" if promoter_name else f"{company_name} wilful defaulter CIBIL NPA India",
        f"{company_name} CIBIL defaulter list bank NPA India",
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
            print(f"[RBIListCheck] Query failed: {exc}")

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 4))

    state["rbi_list_findings"] = all_findings
    state["status_message"] = f"RBI list check complete. {len(all_findings)} findings."

    return state
