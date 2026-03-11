"""
Decisions API Endpoints
Stages 5-6 — CM and Sanctioning Authority decisions.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from schemas.decisions import (
    DecisionRequest, DecisionRecord, SanctionLetterRequest,
    SanctionLetterResponse, DecisionPackResponse
)
from schemas.common import APIResponse, DecisionAction, ApplicationStage
from middleware.auth import get_current_user, require_credit_manager, require_sanctioning, UserContext
from services.supabase_client import get_supabase
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/decisions", tags=["Decisions"])


@router.post("/{application_id}", response_model=APIResponse)
async def submit_decision(
    application_id: str,
    request: DecisionRequest,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
):
    """Submit approval/rejection decision (CM or Sanctioning Authority)."""
    try:
        supabase = get_supabase()
        decision_id = str(uuid.uuid4())

        record = {
            "id": decision_id,
            "application_id": application_id,
            "action": request.action.value,
            "decided_by": user.uid,
            "decided_by_role": request.decided_by_role,
            "approved_limit": request.approved_limit,
            "approved_rate": request.approved_rate,
            "approved_tenure_months": request.approved_tenure_months,
            "conditions": request.conditions,
            "covenants": request.covenants,
            "rejection_reason": request.rejection_reason,
            "return_instructions": request.return_instructions,
            "remarks": request.remarks,
        }
        supabase.table("loan_decisions").insert(record).execute()

        # Update application stage
        stage_map = {
            DecisionAction.APPROVE: ApplicationStage.POST_SANCTION.value,
            DecisionAction.APPROVE_WITH_MODIFICATIONS: ApplicationStage.POST_SANCTION.value,
            DecisionAction.REJECT: ApplicationStage.POST_SANCTION.value,
            DecisionAction.RETURN_FOR_REVIEW: ApplicationStage.CREDIT_ANALYSIS.value,
            DecisionAction.RETURN_FOR_DD: ApplicationStage.FIELD_VISIT.value,
        }
        new_stage = stage_map.get(request.action, ApplicationStage.POST_SANCTION.value)
        supabase.table("applications").update({
            "current_stage": new_stage,
        }).eq("id", application_id).execute()

        # Generate sanction letter on approval
        if request.action in [DecisionAction.APPROVE, DecisionAction.APPROVE_WITH_MODIFICATIONS]:
            background_tasks.add_task(generate_sanction_letter_bg, application_id, decision_id)

        # Audit log
        supabase.table("audit_logs").insert({
            "id": str(uuid.uuid4()),
            "entity_type": "decision",
            "entity_id": decision_id,
            "action": f"decision_{request.action.value}",
            "performed_by": user.uid,
            "details": {"application_id": application_id, "role": request.decided_by_role},
        }).execute()

        return APIResponse(success=True, message=f"Decision recorded: {request.action.value}", data={"decision_id": decision_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def generate_sanction_letter_bg(application_id: str, decision_id: str):
    """Background: Generate sanction letter. TODO: Replace with sanction_letter agent."""
    try:
        # Stub for agents/nodes/sanction_letter.py
        pass
    except Exception as e:
        print(f"[ERROR] Sanction letter generation failed: {e}")


@router.get("/{application_id}", response_model=APIResponse)
async def get_decisions(application_id: str, user: UserContext = Depends(get_current_user)):
    """Get all decisions for an application."""
    try:
        supabase = get_supabase()
        result = supabase.table("loan_decisions").select("*").eq(
            "application_id", application_id
        ).order("created_at", desc=True).execute()
        return APIResponse(success=True, data=result.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}/decision-pack", response_model=APIResponse)
async def get_decision_pack(application_id: str, user: UserContext = Depends(get_current_user)):
    """Get one-screen Decision Pack for Sanctioning Authority (PRD Section 6, Portal 5)."""
    try:
        supabase = get_supabase()
        app = supabase.table("applications").select("*").eq("id", application_id).single().execute()
        risk = supabase.table("risk_scores").select("*").eq("application_id", application_id).execute()
        cam = supabase.table("cam_documents").select("id, cam_docx_url").eq("application_id", application_id).order("created_at", desc=True).limit(1).execute()
        decisions = supabase.table("loan_decisions").select("*").eq("application_id", application_id).eq("decided_by_role", "credit_manager").order("created_at", desc=True).limit(1).execute()

        risk_data = risk.data[0] if risk.data else {}
        shap_vals = risk_data.get("shap_values", [])
        top_risks = [s["feature_name"] for s in shap_vals if s.get("direction") == "increases_risk"][:3]
        top_strengths = [s["feature_name"] for s in shap_vals if s.get("direction") == "decreases_risk"][:3]

        pack = {
            "application_id": application_id,
            "company_name": app.data.get("company_name"),
            "sector": app.data.get("sector"),
            "loan_type": app.data.get("loan_type"),
            "loan_amount_requested": app.data.get("loan_amount_requested"),
            "risk_grade": risk_data.get("risk_grade"),
            "probability_of_default": risk_data.get("probability_of_default"),
            "top_risk_factors": top_risks,
            "top_strengths": top_strengths,
            "policy_exceptions": [],
            "cam_url": cam.data[0].get("cam_docx_url") if cam.data else None,
            "cm_decision": decisions.data[0] if decisions.data else None,
        }
        return APIResponse(success=True, data=pack)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{application_id}/sanction-letter", response_model=APIResponse)
async def generate_sanction_letter(
    application_id: str,
    request: SanctionLetterRequest,
    user: UserContext = Depends(require_sanctioning),
):
    """Generate sanction letter (python-docx)."""
    try:
        from services.cam_generator import generate_sanction_letter_doc
        result = generate_sanction_letter_doc(application_id, request.format)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
