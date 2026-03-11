"""
Pre-Qualification API Endpoint
Stage 0 — Instant eligibility check using Logistic Regression model.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from schemas.pre_qual import PreQualRequest, PreQualResponse, PreQualFeatures
from schemas.common import APIResponse, EligibilityTier
from schemas.applications import ApplicationCreate
from middleware.auth import get_current_user, UserContext
from services.supabase_client import get_supabase
from ml.pre_qual_model import run_pre_qual_scoring
from typing import Dict, Any
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/pre-qual", tags=["Pre-Qualification"])


# --- Sector risk weights (dynamic from DB, fallback hardcoded) ---
DEFAULT_SECTOR_WEIGHTS: Dict[str, float] = {
    "Manufacturing": 1.0,
    "IT/Software": 0.8,
    "NBFC": 2.0,
    "Infrastructure": 1.5,
    "Trading": 1.8,
    "Pharmaceuticals": 0.9,
    "Textiles": 1.4,
    "Real Estate": 2.5,
    "Agriculture": 1.6,
    "Services": 1.0,
}

LOAN_TYPE_FEASIBILITY = {
    "CC": 1.0,
    "TL": 0.9,
    "WCTL": 0.85,
    "BG": 0.8,
    "LC": 0.8,
}


async def get_sector_risk_weight(sector: str) -> float:
    """Get sector risk weight from DB config, fallback to defaults."""
    try:
        supabase = get_supabase()
        result = supabase.table("sector_benchmarks").select("risk_weight").eq("sector", sector).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]["risk_weight"]
    except Exception:
        pass
    return DEFAULT_SECTOR_WEIGHTS.get(sector, 1.2)


def engineer_pre_qual_features(request: PreQualRequest, sector_weight: float) -> PreQualFeatures:
    """Transform raw input into the 8 ML features (PRD 4.1)."""
    current_year = datetime.now().year
    return PreQualFeatures(
        sector_risk_weight=sector_weight,
        turnover_to_loan_ratio=min(request.annual_turnover / max(request.loan_amount_requested, 1), 5.0),
        years_in_business=request.years_in_business,
        existing_debt_load_ratio=min(request.existing_debt / max(request.annual_turnover, 1), 10.0),
        npa_flag=1 if request.is_npa else 0,
        loan_type_feasibility=LOAN_TYPE_FEASIBILITY.get(request.loan_type.value, 0.85),
        company_incorporation_age=min(current_year - request.incorporation_year, 100),
        group_company_status=1 if request.is_group_company else 0,
    )


@router.post("/check", response_model=APIResponse)
async def check_pre_qualification(
    request: PreQualRequest,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
):
    """
    Run pre-qualification check. Returns eligibility score, tier, and reasons.
    If eligible/borderline, auto-creates a loan application.
    """
    try:
        # Get sector risk weight from config
        sector_weight = await get_sector_risk_weight(request.sector)

        # Engineer features
        features = engineer_pre_qual_features(request, sector_weight)

        # Run ML model
        result: PreQualResponse = run_pre_qual_scoring(features)
        result.sector_risk_weight = sector_weight

        # If eligible or borderline, create application
        if result.eligibility_tier in [EligibilityTier.ELIGIBLE, EligibilityTier.BORDERLINE]:
            app_id = str(uuid.uuid4())
            result.application_id = app_id

            # Create application in background
            background_tasks.add_task(
                create_application_record,
                app_id=app_id,
                request=request,
                pre_qual_score=result.score,
                user_uid=user.uid,
            )

        return APIResponse(
            success=True,
            message=f"Pre-qualification: {result.eligibility_tier.value}",
            data=result.model_dump(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pre-qualification check failed: {str(e)}")


async def create_application_record(
    app_id: str,
    request: PreQualRequest,
    pre_qual_score: float,
    user_uid: str,
):
    """Background task: create loan application in Supabase."""
    try:
        supabase = get_supabase()
        supabase.table("applications").insert({
            "id": app_id,
            "company_name": request.company_name,
            "cin_number": request.cin_number,
            "sector": request.sector,
            "loan_type": request.loan_type.value,
            "loan_amount_requested": request.loan_amount_requested,
            "annual_turnover": request.annual_turnover,
            "years_in_business": request.years_in_business,
            "contact_email": request.contact_email,
            "contact_phone": request.contact_phone,
            "borrower_uid": user_uid,
            "pre_qual_score": pre_qual_score,
            "current_stage": "document_upload",
            "is_active": True,
        }).execute()
    except Exception as e:
        print(f"[ERROR] Failed to create application: {e}")


@router.get("/sector-weights", response_model=APIResponse)
async def get_all_sector_weights(user: UserContext = Depends(get_current_user)):
    """Get all sector risk weights from config."""
    try:
        supabase = get_supabase()
        result = supabase.table("sector_benchmarks").select("sector, risk_weight").execute()
        weights = {row["sector"]: row["risk_weight"] for row in result.data} if result.data else DEFAULT_SECTOR_WEIGHTS
        return APIResponse(success=True, data=weights)
    except Exception:
        return APIResponse(success=True, data=DEFAULT_SECTOR_WEIGHTS)
