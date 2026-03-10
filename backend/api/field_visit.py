"""
Field Visit API Endpoint
Stage 3 — Field visit submission + qualitative scoring.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from schemas.field_visit import FieldVisitSubmission, FieldVisitRecord, QualitativeRiskAdjustment
from schemas.common import APIResponse
from middleware.auth import get_current_user, require_analyst, UserContext
from services.supabase_client import get_supabase
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/field-visit", tags=["Field Visit"])


@router.post("", response_model=APIResponse)
async def submit_field_visit(
    request: FieldVisitSubmission,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_analyst),
):
    """
    Submit field visit observations.
    Triggers qualitative scoring agent in background.
    """
    try:
        supabase = get_supabase()
        visit_id = str(uuid.uuid4())
        
        record = {
            "id": visit_id,
            "application_id": request.application_id,
            "visit_date": request.visit_date.isoformat(),
            "visited_by": user.uid,
            "capacity_utilization_percent": request.capacity_utilization_percent,
            "factory_condition": request.factory_condition,
            "inventory_level": request.inventory_level,
            "machinery_condition": request.machinery_condition,
            "management_cooperation": request.management_cooperation,
            "management_quality": request.management_quality,
            "promoter_presence": request.promoter_presence,
            "observations": request.observations,
            "photo_urls": request.photo_urls,
            "voice_record_url": request.voice_record_url,
            "additional_notes": request.additional_notes,
        }
        
        supabase.table("field_visit_notes").insert(record).execute()
        
        # Trigger qualitative scoring agent in background
        background_tasks.add_task(
            run_qualitative_scoring,
            application_id=request.application_id,
            visit_id=visit_id,
            observations=request.observations,
            structured_data=record,
        )
        
        # Log audit
        supabase.table("audit_logs").insert({
            "id": str(uuid.uuid4()),
            "entity_type": "field_visit",
            "entity_id": visit_id,
            "action": "field_visit_submitted",
            "performed_by": user.uid,
            "details": {"application_id": request.application_id},
        }).execute()
        
        return APIResponse(
            success=True,
            message="Field visit submitted. Qualitative scoring in progress.",
            data={"visit_id": visit_id}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Field visit submission failed: {str(e)}")


async def run_qualitative_scoring(
    application_id: str,
    visit_id: str,
    observations: str,
    structured_data: dict,
):
    """
    Background task: Run qualitative scoring agent on field visit data.
    TODO: Replace with actual LangGraph qualitative_scoring_node call.
    """
    try:
        # Placeholder: Will be replaced by agents/nodes/qualitative_scoring.py
        # The agent converts free-text observations to risk adjustments:
        # "Capacity 35%" -> -18 points
        # "Management evasive" -> +8 points
        
        supabase = get_supabase()
        supabase.table("field_visit_notes").update({
            "risk_adjustments": {
                "status": "pending_agent",
                "message": "Qualitative scoring agent will process this"
            }
        }).eq("id", visit_id).execute()
        
    except Exception as e:
        print(f"[ERROR] Qualitative scoring failed: {e}")


@router.get("/{application_id}", response_model=APIResponse)
async def get_field_visit(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Get field visit data for an application."""
    try:
        supabase = get_supabase()
        result = supabase.table("field_visit_notes").select("*").eq(
            "application_id", application_id
        ).order("created_at", desc=True).execute()
        
        return APIResponse(success=True, data=result.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{visit_id}", response_model=APIResponse)
async def update_field_visit(
    visit_id: str,
    request: FieldVisitSubmission,
    user: UserContext = Depends(require_analyst),
):
    """Update an existing field visit record."""
    try:
        supabase = get_supabase()
        
        update_data = {
            "capacity_utilization_percent": request.capacity_utilization_percent,
            "factory_condition": request.factory_condition,
            "inventory_level": request.inventory_level,
            "machinery_condition": request.machinery_condition,
            "management_cooperation": request.management_cooperation,
            "management_quality": request.management_quality,
            "promoter_presence": request.promoter_presence,
            "observations": request.observations,
            "photo_urls": request.photo_urls,
            "voice_record_url": request.voice_record_url,
            "additional_notes": request.additional_notes,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        supabase.table("field_visit_notes").update(update_data).eq("id", visit_id).execute()
        
        return APIResponse(success=True, message="Field visit updated")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
