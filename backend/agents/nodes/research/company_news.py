"""
Research: Company News Node — Tavily search for adverse company news.

3 queries for fraud/scam, litigation, and regulatory enforcement.
Severity scoring based on keyword hits.
"""

import re
from datetime import datetime
from typing import Any, Dict, List
from agents.state import CreditApplicationState
from services.tavily_service import get_tavily_client


# ---------------------------------------------------------------------------
# Severity scoring rules
# ---------------------------------------------------------------------------

_SEVERITY_RULES = [
    # (pattern, severity, risk_impact)
    (r"(?:ED\s*probe|enforcement\s*directorate|fraud|scam|money\s*laundering)", "critical", 22),
    (r"(?:NPA|default(?:er|ed)?|restructured|stressed\s*asset)", "high", 18),
    (r"(?:court\s*case|litigation|FIR|criminal|arrested)", "high", 14),
    (r"(?:regulatory|penalty|SEBI\s*notice|compliance|fine)", "medium", 9),
]


def _score_finding(title: str, content: str) -> tuple:
    """Return (severity, risk_impact) based on keyword matching."""
    combined = f"{title} {content}".lower()
    for pattern, severity, impact in _SEVERITY_RULES:
        if re.search(pattern, combined, re.IGNORECASE):
            return severity, impact
    return "low", 2


def _make_finding(result: Dict, source_type: str = "news") -> Dict[str, Any]:
    """Convert Tavily result to standard finding schema."""
    title = result.get("title", "")
    content = result.get("content", "")
    severity, risk_impact = _score_finding(title, content)

    # Estimate date
    published = result.get("published_date", "")
    if not published:
        published = datetime.utcnow().strftime("%Y-%m-%d")
    elif len(published) > 10:
        published = published[:10]

    return {
        "source_type": source_type,
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

async def company_news_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    Search for adverse company news using 3 Tavily queries.
    Deduplicates by URL. Stores findings in state.
    """
    state["current_node"] = "company_news"
    state["status_message"] = "Searching company news..."

    company_name = state.get("company_name", "")
    if not company_name:
        state["company_news"] = []
        return state

    # Build queries
    promoter_name = ""
    # Try to get promoter from KYC data
    kyc_data = state.get("kyc_data") or []
    for kyc in kyc_data:
        directors = (kyc.get("extracted_data") or {}).get("directors") or []
        if directors:
            promoter_name = directors[0].get("name", "")
            break

    queries = [
        f"{company_name} fraud scam NPA default India",
        f"{company_name} {promoter_name} litigation court case India" if promoter_name else f"{company_name} litigation court case India",
        f"{company_name} RBI SEBI enforcement directorate India",
    ]

    # Run all 3 queries
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
                    all_findings.append(_make_finding(r, "news"))
        except Exception as exc:
            print(f"[CompanyNews] Query failed: {exc}")

    # Sort by severity (critical first)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 4))

    state["company_news"] = all_findings
    state["status_message"] = f"Found {len(all_findings)} company news items."

    return state
