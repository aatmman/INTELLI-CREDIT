"""
Analysis API Endpoints
Stage 4 — Financial, GST, Banking, Research, Timeline data for 6-tab workspace.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from schemas.analysis import (
    ExtractedFinancials, GSTAnalysisResponse, BankingAnalysisResponse,
    ResearchResponse, RiskTimelineResponse, WhatIfRequest, WhatIfResponse
)
from schemas.common import APIResponse
from middleware.auth import get_current_user, require_analyst, UserContext
from services.supabase_client import get_supabase

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


# --- Tab 1: Financial Analysis ---

@router.get("/{application_id}/financial", response_model=APIResponse)
async def get_financial_analysis(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Get 3-year financial analysis (P&L, BS, CF, ratios, benchmarks, charts data).
    Tab 1 of the Analysis Portal.
    """
    try:
        supabase = get_supabase()
        
        # Get extracted financials
        financials = supabase.table("extracted_financials").select("*").eq(
            "application_id", application_id
        ).order("financial_year", desc=False).execute()
        
        # Get sector benchmarks for comparison
        app = supabase.table("loan_applications").select("sector").eq(
            "id", application_id
        ).single().execute()
        
        benchmarks = {}
        if app.data:
            bench_result = supabase.table("sector_benchmarks").select("*").eq(
                "sector", app.data["sector"]
            ).execute()
            if bench_result.data:
                benchmarks = bench_result.data[0]
        
        return APIResponse(
            success=True,
            data={
                "financials": financials.data,
                "benchmarks": benchmarks,
                "application_id": application_id,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Tab 2: GST & Banking ---

@router.get("/{application_id}/gst", response_model=APIResponse)
async def get_gst_analysis(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Get 24-month GST analysis (GSTR-3B, GSTR-1, ITC, circular trading score).
    Tab 2 of the Analysis Portal.
    """
    try:
        supabase = get_supabase()
        result = supabase.table("gst_monthly_data").select("*").eq(
            "application_id", application_id
        ).order("month", desc=False).execute()
        
        # Get circular trading score from risk_scores
        risk = supabase.table("risk_scores").select(
            "circular_trading_score, gst_score"
        ).eq("application_id", application_id).execute()
        
        return APIResponse(
            success=True,
            data={
                "monthly_data": result.data,
                "risk_scores": risk.data[0] if risk.data else {},
                "application_id": application_id,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}/banking", response_model=APIResponse)
async def get_banking_analysis(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Get 12-month banking analysis (credits, debits, bounces, behavior score).
    Tab 2 of the Analysis Portal.
    """
    try:
        supabase = get_supabase()
        result = supabase.table("bank_statement_data").select("*").eq(
            "application_id", application_id
        ).order("month", desc=False).execute()
        
        # Get banking score
        risk = supabase.table("risk_scores").select(
            "banking_conduct_score"
        ).eq("application_id", application_id).execute()
        
        return APIResponse(
            success=True,
            data={
                "monthly_data": result.data,
                "banking_score": risk.data[0] if risk.data else {},
                "application_id": application_id,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Tab 3: External Research ---

@router.get("/{application_id}/research", response_model=APIResponse)
async def get_research_findings(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Get external research findings (Tavily, MCA, e-Courts, RBI lists).
    Tab 3 of the Analysis Portal.
    """
    try:
        supabase = get_supabase()
        result = supabase.table("research_findings").select("*").eq(
            "application_id", application_id
        ).order("severity", desc=True).execute()
        
        findings = result.data or []
        
        return APIResponse(
            success=True,
            data={
                "findings": findings,
                "total_findings": len(findings),
                "critical_count": sum(1 for f in findings if f.get("severity") == "critical"),
                "high_count": sum(1 for f in findings if f.get("severity") == "high"),
                "application_id": application_id,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{application_id}/research/trigger", response_model=APIResponse)
async def trigger_research(
    application_id: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_analyst),
):
    """
    Trigger external research agent for an application.
    Runs in background: Tavily, MCA, e-Courts, RBI lists, sector research.
    """
    try:
        # TODO: Trigger research_agent_subgraph from LangGraph
        background_tasks.add_task(run_research_agent, application_id)
        
        return APIResponse(
            success=True,
            message="Research agent triggered. Results will appear in real-time.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_research_agent(application_id: str):
    """Background: Run research agent subgraph."""
    try:
        import asyncio
        from agents.nodes.research.company_news import company_news_node
        from agents.nodes.research.mca_check import mca_check_node
        from agents.nodes.research.ecourts_check import ecourts_check_node
        from agents.nodes.research.sector_research import sector_research_node
        from agents.nodes.research.rbi_list_check import rbi_list_check_node
        from agents.nodes.research.aggregator import research_aggregator_node

        state = {"application_id": application_id}
        
        # Run parallel nodes
        results = await asyncio.gather(
            company_news_node(state.copy()),
            mca_check_node(state.copy()),
            ecourts_check_node(state.copy()),
            sector_research_node(state.copy()),
            rbi_list_check_node(state.copy()),
            return_exceptions=True
        )

        merged_state = {"application_id": application_id}
        for res in results:
            if isinstance(res, dict):
                merged_state.update(res)
            else:
                print(f"[Research] Node yielded exception: {res}")

        # Run aggregator
        await research_aggregator_node(merged_state)
        print(f"[Research] Completed research agent for {application_id}")
    except Exception as e:
        print(f"[ERROR] Research agent failed: {e}")


# --- Tab 4: Risk Timeline (DIFFERENTIATOR) ---

@router.get("/{application_id}/timeline", response_model=APIResponse)
async def get_risk_timeline(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Get chronological risk timeline aggregating ALL sources.
    Tab 4 of the Analysis Portal — KEY DIFFERENTIATOR.
    """
    try:
        supabase = get_supabase()
        
        # Aggregate timeline events from multiple sources
        # TODO: Replace with actual risk_timeline_builder output
        
        # For now, check if timeline data exists in risk_scores
        result = supabase.table("risk_scores").select(
            "timeline_data"
        ).eq("application_id", application_id).execute()
        
        timeline_data = result.data[0].get("timeline_data", []) if result.data else []
        
        return APIResponse(
            success=True,
            data={
                "events": timeline_data,
                "total_events": len(timeline_data),
                "application_id": application_id,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Tab 6: What-If Simulator ---

@router.post("/{application_id}/what-if", response_model=APIResponse)
async def run_what_if_simulation(
    application_id: str,
    request: WhatIfRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    What-If simulator: Adjust input features, see how score changes.
    Tab 6 of the Analysis Portal.
    """
    try:
        from ml.credit_risk_model import run_what_if_scoring
        
        result = run_what_if_scoring(application_id, request.adjusted_features)
        
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Trigger Full Analysis Pipeline ---

@router.post("/{application_id}/run-all", response_model=APIResponse)
async def trigger_full_analysis(
    application_id: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_analyst),
):
    """
    Trigger the full analysis pipeline (all agents + models).
    This runs the master CreditAppraisalGraph for Stage 4.
    """
    try:
        # TODO: Trigger full CreditAppraisalGraph from agents/graph.py
        background_tasks.add_task(run_full_analysis_pipeline, application_id)
        
        return APIResponse(
            success=True,
            message="Full analysis pipeline started. Track progress via real-time updates.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_full_analysis_pipeline(application_id: str):
    """Background: Run the full CreditAppraisalGraph."""
    try:
        from agents.graph import run_graph
        await run_graph(application_id)
    except Exception as e:
        print(f"[ERROR] Full analysis pipeline failed: {e}")
