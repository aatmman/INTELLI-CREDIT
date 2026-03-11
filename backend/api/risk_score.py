"""
Risk Score API Endpoints
Stage 5 — XGBoost scoring + SHAP + policy checks.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from schemas.risk_score import RiskScoreResponse, PolicyCheckResponse
from schemas.common import APIResponse
from middleware.auth import get_current_user, require_credit_manager, UserContext
from services.supabase_client import get_supabase
from ml.credit_risk_model import compute_credit_risk_score
from ml.feature_engineering import build_xgboost_features
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/risk-score", tags=["Risk Scoring"])


@router.post("/compute/{application_id}", response_model=APIResponse)
async def compute_risk_score(
    application_id: str,
    background_tasks: BackgroundTasks,
    include_shap: bool = True,
    user: UserContext = Depends(require_credit_manager),
):
    """Compute XGBoost credit risk score with SHAP explainability."""
    try:
        supabase = get_supabase()
        features = await build_xgboost_features(application_id)
        result = compute_credit_risk_score(application_id, features, include_shap)

        score_record = {
            "id": str(uuid.uuid4()),
            "application_id": application_id,
            "final_risk_score": result.final_risk_score,
            "risk_grade": result.risk_grade.value if result.risk_grade else None,
            "probability_of_default": result.probability_of_default,
            "recommended_limit": result.recommended_limit,
            "recommended_rate": result.recommended_rate,
            "shap_values": [s.model_dump() for s in result.shap_values],
            "features_used": result.features_used,
            "model_version": result.model_version,
            "scored_at": datetime.utcnow().isoformat(),
        }
        supabase.table("risk_scores").upsert(score_record, on_conflict="application_id").execute()
        supabase.table("loan_applications").update({
            "final_risk_grade": result.risk_grade.value if result.risk_grade else None,
        }).eq("id", application_id).execute()

        background_tasks.add_task(run_policy_checks, application_id)

        return APIResponse(success=True, data=result.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}", response_model=APIResponse)
async def get_risk_score(application_id: str, user: UserContext = Depends(get_current_user)):
    """Get computed risk score + SHAP values."""
    try:
        supabase = get_supabase()
        result = supabase.table("risk_scores").select("*").eq("application_id", application_id).execute()
        return APIResponse(success=True, data=result.data[0] if result.data else None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}/policy-checks", response_model=APIResponse)
async def get_policy_checks(application_id: str, user: UserContext = Depends(get_current_user)):
    """Get policy compliance results."""
    try:
        supabase = get_supabase()
        result = supabase.table("risk_scores").select("policy_check_results").eq("application_id", application_id).execute()
        return APIResponse(success=True, data=result.data[0].get("policy_check_results") if result.data else None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_policy_checks(application_id: str):
    """Background: Run policy rules from DB. TODO: Replace with policy_check agent."""
    try:
        supabase = get_supabase()
        rules = supabase.table("policy_rules").select("*").eq("is_active", True).execute()
        checks = []
        for rule in (rules.data or []):
            checks.append({
                "rule_id": rule["id"],
                "rule_name": rule.get("rule_name", ""),
                "status": "pending",
                "is_hard_rule": rule.get("is_hard_rule", False),
            })
        supabase.table("risk_scores").update({
            "policy_check_results": {"checks": checks, "total_checks": len(checks)}
        }).eq("application_id", application_id).execute()
    except Exception as e:
        print(f"[ERROR] Policy checks failed: {e}")


@router.get("/{application_id}/rate-recommendation", response_model=APIResponse)
async def get_rate_recommendation(application_id: str, user: UserContext = Depends(get_current_user)):
    """Get recommended interest rate from rate_config table."""
    try:
        supabase = get_supabase()
        score = supabase.table("risk_scores").select("risk_grade").eq("application_id", application_id).execute()
        if not score.data or not score.data[0].get("risk_grade"):
            raise HTTPException(status_code=404, detail="Risk grade not computed")
        risk_grade = score.data[0]["risk_grade"]
        rate = supabase.table("rate_config").select("*").eq("risk_grade", risk_grade).execute()
        return APIResponse(success=True, data={"risk_grade": risk_grade, "rate_config": rate.data[0] if rate.data else None})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
