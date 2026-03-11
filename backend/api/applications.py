"""
Application Management API Endpoints
Core CRUD + stage transitions for loan applications.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.applications import (
    ApplicationCreate, ApplicationUpdate, ApplicationStageTransition,
    ApplicationRecord, ApplicationListItem
)
from schemas.common import APIResponse, ApplicationStage
from middleware.auth import get_current_user, UserContext
from services.supabase_client import get_supabase
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/applications", tags=["Applications"])


@router.post("", response_model=APIResponse)
async def create_application(request: ApplicationCreate, user: UserContext = Depends(get_current_user)):
    """Create a new loan application."""
    try:
        supabase = get_supabase()
        app_id = str(uuid.uuid4())
        record = {
            "id": app_id,
            "company_name": request.company_name,
            "cin_number": request.cin_number,
            "pan_number": request.pan_number,
            "sector": request.sector,
            "loan_type": request.loan_type.value,
            "loan_amount_requested": request.loan_amount_requested,
            "annual_turnover": request.annual_turnover,
            "years_in_business": request.years_in_business,
            "contact_email": request.contact_email,
            "contact_phone": request.contact_phone,
            "borrower_uid": request.borrower_uid,
            "pre_qual_score": request.pre_qual_score,
            "current_stage": ApplicationStage.DOCUMENT_UPLOAD.value,
            "is_active": True,
        }
        supabase.table("applications").insert(record).execute()
        return APIResponse(success=True, message="Application created", data={"application_id": app_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=APIResponse)
async def list_applications(
    stage: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
):
    """List applications (filtered by role and optional stage)."""
    try:
        supabase = get_supabase()
        query = supabase.table("applications").select("*", count="exact")

        # Role-based filtering
        if user.role == "borrower":
            query = query.eq("borrower_uid", user.uid)
        elif user.role == "rm":
            # RM sees all applications in the pipeline so they can pick up new requests
            pass
        elif user.role == "analyst":
            query = query.eq("assigned_analyst", user.uid)
        elif user.role == "credit_manager":
            query = query.eq("assigned_cm", user.uid)

        if stage:
            query = query.eq("current_stage", stage)

        query = query.eq("is_active", True).order("created_at", desc=True)
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)
        result = query.execute()

        return APIResponse(success=True, data={
            "items": result.data,
            "total": result.count or len(result.data),
            "page": page,
            "page_size": page_size,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}", response_model=APIResponse)
async def get_application(application_id: str, user: UserContext = Depends(get_current_user)):
    """Get full application details."""
    try:
        supabase = get_supabase()
        result = supabase.table("applications").select("*").eq("id", application_id).single().execute()
        return APIResponse(success=True, data=result.data)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Application not found")


@router.patch("/{application_id}", response_model=APIResponse)
async def update_application(
    application_id: str, request: ApplicationUpdate, user: UserContext = Depends(get_current_user)
):
    """Update application fields."""
    try:
        supabase = get_supabase()
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("applications").update(update_data).eq("id", application_id).execute()
        return APIResponse(success=True, message="Application updated")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{application_id}/stage", response_model=APIResponse)
async def transition_stage(
    application_id: str, request: ApplicationStageTransition, user: UserContext = Depends(get_current_user)
):
    """Move application to next stage."""
    try:
        supabase = get_supabase()
        app = supabase.table("applications").select("current_stage, stage_history").eq("id", application_id).single().execute()
        history = app.data.get("stage_history") or []
        history.append({
            "from_stage": app.data["current_stage"],
            "to_stage": request.target_stage.value,
            "transitioned_by": user.uid,
            "remarks": request.remarks,
            "timestamp": datetime.utcnow().isoformat(),
        })
        supabase.table("applications").update({
            "current_stage": request.target_stage.value,
            "stage_history": history,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", application_id).execute()

        # Audit log
        supabase.table("audit_logs").insert({
            "id": str(uuid.uuid4()),
            "entity_type": "application",
            "entity_id": application_id,
            "action": "stage_transition",
            "performed_by": user.uid,
            "details": {"from": app.data["current_stage"], "to": request.target_stage.value},
        }).execute()

        return APIResponse(success=True, message=f"Stage transitioned to {request.target_stage.value}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
