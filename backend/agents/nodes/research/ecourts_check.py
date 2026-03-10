"""
Research: eCourts Check Node — Tavily search for litigation history.

3 queries for court cases, DRT proceedings, and criminal cases.
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
    (r"(?:DRT|debt\s*recovery\s*tribunal|NCLT|insolvency)", "critical", 25),
    (r"(?:criminal\s*case|arrested|FIR|CBI|fraud\s*case)", "critical", 22),
    (r"(?:crore|lakh|recovery\s*suit|winding\s*up\s*petition)", "high", 12),
    (r"(?:civil\s*suit|commercial\s*court|arbitration|cheque\s*bounce)", "medium", 6),
    (r"(?:consumer\s*(?:forum|court)|labour\s*court|RERA)", "low", 4),
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
        "source_type": "ecourts",
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

async def ecourts_check_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    Search eCourts for litigation, DRT, and criminal cases.
    3 Tavily queries, deduped by URL.
    """
    state["current_node"] = "ecourts_check"
    state["status_message"] = "Checking court records..."

    company_name = state.get("company_name", "")
    if not company_name:
        state["ecourts_findings"] = []
        return state

    # Get promoter name from KYC data
    promoter_name = ""
    kyc_data = state.get("kyc_data") or []
    for kyc in kyc_data:
        directors = (kyc.get("extracted_data") or {}).get("directors") or []
        if directors:
            promoter_name = directors[0].get("name", "")
            break

    queries = [
        f"{company_name} court case ecourts.gov.in suit filed",
        f"{company_name} {promoter_name} civil criminal case India court" if promoter_name else f"{company_name} civil criminal case India court",
        f"{company_name} recovery suit DRT debt tribunal",
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
            print(f"[eCourtsCheck] Query failed: {exc}")

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 4))

    state["ecourts_findings"] = all_findings
    state["status_message"] = f"eCourts check complete. {len(all_findings)} findings."

    return state
