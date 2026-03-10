"""
Tavily Web Research Service
Wrapper for Tavily Search API — used by Research Agent.
"""

from tavily import TavilyClient
from config import settings
from typing import Any, Dict, List, Optional


_tavily_client: Optional[TavilyClient] = None


def get_tavily_client() -> TavilyClient:
    """Get or create Tavily client."""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily_client


async def search_company_news(
    company_name: str,
    max_results: int = 10,
    search_depth: str = "advanced",
) -> List[Dict[str, Any]]:
    """Search for company-related news and articles."""
    client = get_tavily_client()
    query = f"{company_name} India corporate news financial"
    result = client.search(query=query, max_results=max_results, search_depth=search_depth)
    return result.get("results", [])


async def search_mca_filings(company_name: str, cin: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search MCA21 for company filings and charges."""
    client = get_tavily_client()
    query = f"{company_name} MCA Ministry of Corporate Affairs filings charges"
    if cin:
        query += f" CIN {cin}"
    result = client.search(query=query, max_results=5, search_depth="advanced")
    return result.get("results", [])


async def search_ecourts(company_name: str, promoter_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search e-Courts for litigation history."""
    client = get_tavily_client()
    query = f"{company_name} India court case litigation"
    if promoter_name:
        query += f" {promoter_name}"
    result = client.search(query=query, max_results=5, search_depth="advanced")
    return result.get("results", [])


async def search_rbi_lists(company_name: str) -> List[Dict[str, Any]]:
    """Check RBI defaulter/caution lists."""
    client = get_tavily_client()
    query = f"{company_name} RBI defaulter wilful defaulter caution list CIBIL"
    result = client.search(query=query, max_results=5, search_depth="advanced")
    return result.get("results", [])


async def search_sector_news(sector: str) -> List[Dict[str, Any]]:
    """Search for sector-specific headwinds and trends."""
    client = get_tavily_client()
    query = f"India {sector} sector outlook 2025 2026 RBI regulation industry trends"
    result = client.search(query=query, max_results=5, search_depth="advanced")
    return result.get("results", [])
