"""
Master CreditAppraisalGraph — LangGraph state machine.
Connects all 17 agent nodes as per PRD Section 5.

Flow:
  document_ingestion → [5 research nodes PARALLEL] → research_aggregator
  → financial_extraction → gst_analysis → banking_analysis
  → anomaly_detection → qualitative_scoring (INTERRUPT: wait for field visit)
  → ml_scoring → policy_check → risk_timeline
  → cam_writer → END

  sanction_letter → END  (triggered separately after human approval)

State is checkpointed via MemorySaver (local dev) / Supabase (production).
"""

from typing import Any, Dict
from agents.state import CreditApplicationState

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# ── Import all node functions ──

from agents.nodes.document_ingestion import document_ingestion_node
from agents.nodes.financial_extraction import financial_extraction_node
from agents.nodes.gst_analysis import gst_analysis_node
from agents.nodes.banking_analysis import banking_analysis_node
from agents.nodes.qualitative_scoring import qualitative_scoring_node
from agents.nodes.anomaly_detection import anomaly_detection_node
from agents.nodes.risk_timeline import risk_timeline_builder_node
from agents.nodes.ml_scoring import ml_scoring_node
from agents.nodes.policy_check import policy_check_node
from agents.nodes.cam_writer import cam_writer_node
from agents.nodes.sanction_letter import sanction_letter_node

# Research subgraph nodes
from agents.nodes.research.company_news import company_news_node
from agents.nodes.research.mca_check import mca_check_node
from agents.nodes.research.ecourts_check import ecourts_check_node
from agents.nodes.research.sector_research import sector_research_node
from agents.nodes.research.rbi_list_check import rbi_list_check_node
from agents.nodes.research.aggregator import research_aggregator_node


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_credit_appraisal_graph():
    """
    Build the master CreditAppraisalGraph with 17 nodes.

    Pipeline:
      1. document_ingestion
      2. [PARALLEL] company_news | mca_check | ecourts_check | sector_research | rbi_list_check
      3. research_aggregator (fan-in)
      4. financial_extraction
      5. gst_analysis
      6. banking_analysis
      7. anomaly_detection
      8. qualitative_scoring  ← INTERRUPT (human-in-loop: wait for field visit)
      9. ml_scoring
      10. policy_check
      11. risk_timeline
      12. cam_writer → END

    sanction_letter is wired separately (triggered after human approval).
    """
    workflow = StateGraph(CreditApplicationState)

    # ── Add all nodes (17 total) ──

    workflow.add_node("document_ingestion", document_ingestion_node)

    # Research subgraph (5 parallel nodes + aggregator)
    workflow.add_node("company_news", company_news_node)
    workflow.add_node("mca_check", mca_check_node)
    workflow.add_node("ecourts_check", ecourts_check_node)
    workflow.add_node("sector_research", sector_research_node)
    workflow.add_node("rbi_list_check", rbi_list_check_node)
    workflow.add_node("research_aggregator", research_aggregator_node)

    # Analysis pipeline
    workflow.add_node("financial_extraction", financial_extraction_node)
    workflow.add_node("gst_analysis", gst_analysis_node)
    workflow.add_node("banking_analysis", banking_analysis_node)
    workflow.add_node("anomaly_detection", anomaly_detection_node)
    workflow.add_node("qualitative_scoring", qualitative_scoring_node)
    workflow.add_node("ml_scoring", ml_scoring_node)
    workflow.add_node("policy_check", policy_check_node)
    workflow.add_node("risk_timeline", risk_timeline_builder_node)
    workflow.add_node("cam_writer", cam_writer_node)

    # Sanction letter (human-in-loop, triggered separately)
    workflow.add_node("sanction_letter", sanction_letter_node)

    # ── Define edges ──

    # Entry point
    workflow.set_entry_point("document_ingestion")

    # Parallel research fan-out from document_ingestion
    _RESEARCH_NODES = [
        "company_news", "mca_check", "ecourts_check",
        "sector_research", "rbi_list_check",
    ]
    for node in _RESEARCH_NODES:
        workflow.add_edge("document_ingestion", node)
        workflow.add_edge(node, "research_aggregator")

    # Sequential analysis pipeline
    workflow.add_edge("research_aggregator", "financial_extraction")
    workflow.add_edge("financial_extraction", "gst_analysis")
    workflow.add_edge("gst_analysis", "banking_analysis")
    workflow.add_edge("banking_analysis", "anomaly_detection")
    workflow.add_edge("anomaly_detection", "qualitative_scoring")
    workflow.add_edge("qualitative_scoring", "ml_scoring")
    workflow.add_edge("ml_scoring", "policy_check")
    workflow.add_edge("policy_check", "risk_timeline")
    workflow.add_edge("risk_timeline", "cam_writer")
    workflow.add_edge("cam_writer", END)

    # Sanction letter triggered separately (human-in-loop after approval)
    workflow.add_edge("sanction_letter", END)

    # ── Checkpointing ──
    # MemorySaver for local dev — swap to Supabase PostgresSaver in production
    checkpointer = MemorySaver()

    # Compile with interrupt point for human-in-loop field visit
    graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["qualitative_scoring"],  # Wait for field visit data
    )

    return graph


# Module-level compiled graph for import
graph = build_credit_appraisal_graph()


# ---------------------------------------------------------------------------
# Graph execution
# ---------------------------------------------------------------------------

async def run_graph(application_id: str, initial_state: Dict[str, Any] = None):
    """
    Execute the full CreditAppraisalGraph for an application.

    Args:
        application_id: The loan application ID
        initial_state: Optional initial state overrides

    Returns:
        Final CreditApplicationState after all nodes complete
    """
    from datetime import datetime

    state = initial_state or {}
    state["application_id"] = application_id
    state["current_node"] = "document_ingestion"
    state["progress_percent"] = 0
    state["errors"] = []
    state["warnings"] = []
    state["started_at"] = datetime.utcnow().isoformat()

    config = {"configurable": {"thread_id": application_id}}
    result = await graph.ainvoke(state, config=config)
    return result


async def resume_graph(
    application_id: str,
    updated_state: Dict[str, Any] = None,
):
    """
    Resume a paused graph execution (e.g., after field visit data submitted).

    The graph pauses at interrupt_before=["qualitative_scoring"].
    After field visit data is added to state, call this to resume.
    """
    config = {"configurable": {"thread_id": application_id}}

    if updated_state:
        result = await graph.ainvoke(updated_state, config=config)
    else:
        result = await graph.ainvoke(None, config=config)

    return result


async def run_sanction_letter(
    application_id: str,
    state: Dict[str, Any] = None,
):
    """
    Run only the sanction letter node (after human approval).
    This is a separate invocation from the main graph.
    """
    from agents.nodes.sanction_letter import sanction_letter_node

    if state is None:
        state = {"application_id": application_id}
    state["application_id"] = application_id

    result = await sanction_letter_node(state)
    return result
