"""
Groq LLM Service
Wrapper for Groq API (llama-3.3-70b-versatile) calls.
"""

from groq import Groq
from config import settings
from typing import Any, Dict, List, Optional
import json


_groq_client: Optional[Groq] = None

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_groq_client() -> Groq:
    """Get or create Groq client."""
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


async def groq_chat_completion(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    response_format: Optional[Dict] = None,
) -> str:
    """Run a chat completion with Groq."""
    client = get_groq_client()
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def groq_json_extraction(
    prompt: str,
    system_prompt: str = "You are a financial data extraction assistant. Extract structured data from the given document text and return valid JSON.",
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Extract structured JSON data using Groq."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    result = await groq_chat_completion(
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    return json.loads(result)


async def groq_cam_generation(
    analysis_data: Dict[str, Any],
    company_name: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Generate CAM narrative using Groq with RAG-sourced data."""
    system_prompt = """You are an expert Indian banking credit analyst writing a Credit Appraisal Memo (CAM).
Write a comprehensive, professional CAM covering the Five Cs of Credit:
1. Character - Promoter background, management quality
2. Capacity - Ability to repay (financials, cash flows)
3. Capital - Net worth, equity contribution
4. Collateral - Security offered
5. Conditions - Industry outlook, economy

CRITICAL: Every factual statement MUST include a source citation in brackets.
Example: "Revenue grew 15% YoY [Source: FY24 P&L Statement]"
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate CAM for {company_name}.\n\nAnalysis Data:\n{json.dumps(analysis_data, indent=2, default=str)}"},
    ]
    return await groq_chat_completion(messages=messages, max_tokens=8192, temperature=0.2)
