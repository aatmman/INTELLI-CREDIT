"""
Agent 6: CAM Writer Node — Generates full Credit Appraisal Memo.

Uses Groq (llama-3.3-70b-versatile via groq_service.py) with 10 separate
section prompts. Every sentence ends with a source citation.
Generates DOCX via cam_generator.py, uploads to Supabase Storage,
stores record in cam_documents table.
"""

import json
from typing import Any, Dict, List
from datetime import datetime

from agents.state import CreditApplicationState
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------

CAM_SECTIONS = [
    "executive_summary",
    "borrower_profile",
    "financial_analysis",
    "banking_conduct",
    "gst_tax_analysis",
    "collateral_assessment",
    "external_intelligence",
    "site_visit_summary",
    "risk_assessment",
    "recommendation",
]

_SECTION_TITLES = {
    "executive_summary": "1. Executive Summary",
    "borrower_profile": "2. Borrower Profile",
    "financial_analysis": "3. Financial Analysis",
    "banking_conduct": "4. Banking Conduct Analysis",
    "gst_tax_analysis": "5. GST & Tax Compliance Analysis",
    "collateral_assessment": "6. Collateral Assessment",
    "external_intelligence": "7. External Intelligence & Research",
    "site_visit_summary": "8. Site Visit Summary",
    "risk_assessment": "9. Risk Assessment & Scoring",
    "recommendation": "10. Recommendation",
}


# ---------------------------------------------------------------------------
# Section prompt builders
# ---------------------------------------------------------------------------

def _build_section_prompt(section: str, state: CreditApplicationState) -> str:
    """Build a focused prompt for each CAM section."""
    company = state.get("company_name", "the borrower")
    loan_type = state.get("loan_type", "credit facility")
    loan_amount = state.get("loan_amount_requested", 0)

    base_rules = """
Rules:
- Write 4-6 sentences of professional credit analysis
- End every factual sentence with [Source: FY24 Audited Financials] or similar
- Use Indian banking terminology (DSCR, NWC, TOL/TNW, etc.)
- Output plain text only, no markdown headers
- Be specific with numbers and cite sources"""

    prompts = {
        "executive_summary": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Executive Summary section for {company} applying for {loan_type} of ₹{loan_amount} Cr.

Company: {company}
Sector: {state.get('sector', 'N/A')}
Loan Type: {loan_type}
Amount Requested: ₹{loan_amount} Cr
Risk Grade: {state.get('risk_grade', 'N/A')}
Final Risk Score: {state.get('final_risk_score', 'N/A')}
Recommended Limit: {state.get('recommended_limit', 'N/A')}
Key Anomalies: {json.dumps(state.get('financial_anomalies', [])[:3], default=str)}
Policy Status: {state.get('policy_overall_status', 'N/A')}

{base_rules}
- Provide a 4-5 sentence overview covering: company background, loan request, key financial metrics, risk assessment, and recommendation.""",

        "borrower_profile": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Borrower Profile section for {company}.

Company: {company}
CIN: {state.get('cin_number', 'N/A')}
PAN: {state.get('pan_number', 'N/A')}
Sector: {state.get('sector', 'N/A')}
Turnover: ₹{state.get('annual_turnover', 'N/A')} Cr
Years in Business: {state.get('years_in_business', 'N/A')}
KYC Data: {json.dumps(state.get('kyc_data', {}), default=str)[:500]}

{base_rules}
- Cover: incorporation details, promoter background, business activity, group structure, track record.""",

        "financial_analysis": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Financial Analysis section based on this data:

3-Year Financials: {json.dumps(state.get('profit_and_loss', {}), default=str)[:800]}
Balance Sheet: {json.dumps(state.get('balance_sheet', {}), default=str)[:800]}
Key Ratios: {json.dumps(state.get('financial_ratios', [])[-3:], default=str)[:800]}
Anomalies Detected: {json.dumps(state.get('financial_anomalies', []), default=str)[:500]}

{base_rules}
- Highlight ratio vs benchmark comparisons
- Flag any anomalies found
- Cover: revenue trend, profitability, leverage, coverage ratios, working capital""",

        "banking_conduct": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Banking Conduct Analysis section.

Banking Monthly Data (latest): {json.dumps((state.get('banking_monthly_data') or [])[-3:], default=str)[:500]}
Banking Conduct Score: {state.get('banking_conduct_score', 'N/A')}/100
Banking Flags: {json.dumps(state.get('banking_flags', []), default=str)[:500]}
Window Dressing Detected: {state.get('window_dressing_detected', False)}
Bounce Rate: computed from monthly data

{base_rules}
- Cover: account conduct, utilization, bounce rate, cash withdrawals, window dressing""",

        "gst_tax_analysis": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the GST & Tax Compliance section.

GST Monthly Data (latest): {json.dumps((state.get('gst_monthly_data') or [])[-3:], default=str)[:500]}
GST vs Financial Ratio: {state.get('gst_vs_financial_ratio', 'N/A')}
GST Flags: {json.dumps(state.get('gst_flags', []), default=str)[:500]}
Circular Trading Score: {state.get('circular_trading_score', 0)}
ITR Data: {json.dumps(state.get('itr_data', {}), default=str)[:300]}

{base_rules}
- Cover: GST filing regularity, ITC patterns, revenue-GST correlation, circular trading risks""",

        "collateral_assessment": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Collateral Assessment section.

Collateral Data: {json.dumps(state.get('collateral_data', {}), default=str)[:500]}
Loan Amount: ₹{loan_amount} Cr

{base_rules}
- Cover: nature of security, valuation, coverage ratio, encumbrances, insurance status
- If no collateral data available, note it as unsecured/clean facility""",

        "external_intelligence": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the External Intelligence section.

Research Findings: {json.dumps((state.get('all_research_findings') or [])[:5], default=str)[:800]}
Research Risk Score: {state.get('research_risk_score', 0)}/100

{base_rules}
- Cover: news sentiment, MCA filings, litigation, RBI/SEBI issues, sector outlook
- For each finding cite [Source: News, Publication Date] or [Source: MCA21]""",

        "site_visit_summary": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Site Visit Summary section.

Field Visit Data: {json.dumps(state.get('field_visit_structured', {}), default=str)[:500]}
Qualitative Score Adjustments: {json.dumps(state.get('qualitative_risk_adjustments', []), default=str)[:500]}

{base_rules}
- Cover: factory condition, capacity utilization, management quality, inventory, worker count
- If no field visit data, state "Field visit pending" """,

        "risk_assessment": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Risk Assessment section.

Final Risk Score: {state.get('final_risk_score', 'N/A')}/100
Risk Grade: {state.get('risk_grade', 'N/A')}
PD: {state.get('probability_of_default', 'N/A')}
Top Risk Factors: {json.dumps(state.get('top_risk_factors', []), default=str)}
Top Strengths: {json.dumps(state.get('top_strengths', []), default=str)}
Anomaly Score: {state.get('anomaly_score', 0)}/100
Timeline Risk Score: {state.get('timeline_risk_score', 0)}/100
Policy Status: {state.get('policy_overall_status', 'N/A')}
Policy Exceptions: {json.dumps(state.get('policy_exceptions', []), default=str)[:500]}
SHAP Values (top 5): {json.dumps((state.get('shap_values') or [])[:5], default=str)[:500]}

{base_rules}
- Cover: overall risk profile, key risk drivers, mitigants, SHAP-based explanations""",

        "recommendation": f"""
You are a senior credit analyst at an Indian bank writing a Credit Appraisal Memo (CAM).
Write the Recommendation section.

Company: {company}
Loan Type: {loan_type}
Amount Requested: ₹{loan_amount} Cr
Recommended Limit: ₹{state.get('recommended_limit', 'N/A')} Cr
Recommended Rate: {state.get('recommended_rate', 'N/A')}%
Risk Grade: {state.get('risk_grade', 'N/A')}
Policy Status: {state.get('policy_overall_status', 'N/A')}
Conditions: {json.dumps(state.get('conditions', []), default=str)}

{base_rules}
- State clear recommendation: Approve / Approve with conditions / Reject
- Specify recommended limit, rate, tenure, and key conditions
- This is the final section — be decisive""",
    }

    return prompts.get(section, f"Write the {section} section for {company}.")


# ---------------------------------------------------------------------------
# Groq section generation
# ---------------------------------------------------------------------------

async def _generate_section(section: str, state: CreditApplicationState) -> str:
    """Generate a single CAM section using Groq."""
    from services.groq_service import groq_chat_completion

    prompt = _build_section_prompt(section, state)
    system = (
        "You are a senior Indian banking credit analyst writing a Credit Appraisal Memo. "
        "Write professional, concise analysis. Every factual claim MUST end with a source "
        "citation in brackets like [Source: FY24 Audited Financials] or [Source: GSTR-3B, Jul 2024]. "
        "Use Indian banking terminology. Output plain text only."
    )

    try:
        result = await groq_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return result.strip()
    except Exception as exc:
        return f"[Section generation failed: {exc}]"


# ---------------------------------------------------------------------------
# DOCX generation + upload
# ---------------------------------------------------------------------------

def _upload_cam_docx(application_id: str, docx_bytes: bytes) -> str:
    """Upload CAM DOCX to Supabase Storage."""
    try:
        supabase = get_supabase()
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = f"cam-documents/{application_id}/CAM_{ts}.docx"
        supabase.storage.from_("documents").upload(path=path, file=docx_bytes)
        url = supabase.storage.from_("documents").get_public_url(path)
        return url
    except Exception as exc:
        print(f"[CAMWriter] Upload failed: {exc}")
        return ""


def _store_cam_record(
    application_id: str,
    sections: Dict[str, str],
    docx_url: str,
) -> None:
    """Store CAM record in cam_documents table."""
    try:
        supabase = get_supabase()
        supabase.table("cam_documents").upsert({
            "application_id": application_id,
            "content": json.dumps(sections, default=str),
            "generated_docx_url": docx_url,
            "generated_at": datetime.utcnow().isoformat(),
            "status": "generated",
        }).execute()
    except Exception as exc:
        print(f"[CAMWriter] DB store failed: {exc}")


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def cam_writer_node(
    state: CreditApplicationState,
) -> CreditApplicationState:
    """
    LangGraph node — CAM Writer.

    1. Generate all 10 CAM sections via separate Groq calls
    2. Assemble into structured dict
    3. Generate DOCX via cam_generator.py
    4. Upload to Supabase Storage
    5. Store record in cam_documents table
    6. Update state
    """
    state["current_node"] = "cam_writer"
    state["progress_percent"] = 88
    state["status_message"] = "Generating Credit Appraisal Memo..."

    errors: list = list(state.get("errors") or [])
    application_id = state.get("application_id", "")

    # ── Generate all 10 sections ──
    sections: Dict[str, str] = {}
    citations: List[Dict[str, str]] = []

    for i, section in enumerate(CAM_SECTIONS):
        state["status_message"] = f"Writing CAM section {i+1}/10: {_SECTION_TITLES[section]}..."
        state["progress_percent"] = 88 + (i * 1)  # 88-98%

        try:
            content = await _generate_section(section, state)
            sections[_SECTION_TITLES[section]] = content

            # Extract citations from [Source: ...] tags
            import re
            for match in re.finditer(r"\[Source:\s*([^\]]+)\]", content):
                citations.append({
                    "section": section,
                    "source": match.group(1).strip(),
                })
        except Exception as exc:
            error_msg = f"[cam_writer] Section {section} failed: {exc}"
            errors.append(error_msg)
            sections[_SECTION_TITLES[section]] = f"[Section unavailable: {exc}]"

    # ── Build full CAM narrative ──
    cam_narrative = "\n\n".join(
        f"{title}\n{'='*len(title)}\n{body}"
        for title, body in sections.items()
    )

    # ── Generate DOCX ──
    state["status_message"] = "Generating CAM document..."
    docx_url = ""
    try:
        from services.cam_generator import generate_cam_document
        cam_content = {"sections": sections}
        docx_bytes = generate_cam_document(application_id, cam_content, format="docx")
        docx_url = _upload_cam_docx(application_id, docx_bytes)
    except Exception as exc:
        errors.append(f"[cam_writer] DOCX generation failed: {exc}")

    # ── Store to DB ──
    if application_id:
        _store_cam_record(application_id, sections, docx_url)

    # ── Update state ──
    state["cam_narrative"] = cam_narrative
    state["cam_sections"] = sections
    state["cam_citations"] = citations
    state["cam_document_url"] = docx_url

    state["errors"] = errors
    state["progress_percent"] = 98
    state["status_message"] = (
        f"CAM generation complete. {len(sections)} sections, "
        f"{len(citations)} citations. "
        f"{'DOCX uploaded.' if docx_url else 'DOCX upload pending.'}"
    )

    return state
