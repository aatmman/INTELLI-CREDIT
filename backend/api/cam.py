"""
CAM (Credit Appraisal Memo) API Endpoints
Stage 4-5 — Generate, view, and export CAM documents.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from schemas.common import APIResponse
from middleware.auth import get_current_user, require_analyst, UserContext
from services.supabase_client import get_supabase
import uuid
from datetime import datetime
import io

router = APIRouter(prefix="/api/cam", tags=["CAM"])


@router.post("/generate/{application_id}", response_model=APIResponse)
async def generate_cam(
    application_id: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_analyst),
):
    """
    Trigger AI-powered CAM generation using Groq + pgvector RAG.
    Every sentence sourced with citations: "[Source: FY24 Balance Sheet]".
    """
    try:
        cam_id = str(uuid.uuid4())
        supabase = get_supabase()
        
        # Create CAM record
        supabase.table("cam_documents").insert({
            "id": cam_id,
            "application_id": application_id,
            "status": "generating",
            "generated_by": user.uid,
        }).execute()
        
        # Trigger CAM writer agent in background
        background_tasks.add_task(
            run_cam_writer_agent,
            application_id=application_id,
            cam_id=cam_id,
        )
        
        return APIResponse(
            success=True,
            message="CAM generation started. Track progress via real-time updates.",
            data={"cam_id": cam_id, "status": "generating"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_cam_writer_agent(application_id: str, cam_id: str):
    """
    Background task: Run CAM writer agent.
    1. Gathers all analysis data from DB
    2. Uses Groq + pgvector RAG to source every statement
    3. Generates structured CAM covering Five Cs of Credit
    4. Creates Word + PDF using python-docx + reportlab
    5. Uploads to Supabase Storage
    6. Updates cam_documents record
    """
    try:
        supabase = get_supabase()
        
        # 1. Gather Data
        app_res = supabase.table("loan_applications").select("*").eq("id", application_id).single().execute()
        company_name = app_res.data.get("company_name", "Unknown Company")
        
        fin_res = supabase.table("extracted_financials").select("*").eq("application_id", application_id).execute()
        gst_res = supabase.table("gst_monthly_data").select("*").eq("application_id", application_id).execute()
        bank_res = supabase.table("bank_statement_data").select("*").eq("application_id", application_id).execute()
        risk_res = supabase.table("risk_scores").select("*").eq("application_id", application_id).execute()
        
        analysis_data = {
            "loan_details": app_res.data,
            "financials": fin_res.data,
            "gst": gst_res.data,
            "banking": bank_res.data,
            "risk_score": risk_res.data[0] if risk_res.data else {}
        }
        
        # 2. Call Groq
        from services.groq_service import groq_cam_generation
        cam_text = await groq_cam_generation(analysis_data, company_name)
        
        cam_content = {"sections": {"Detailed Memo": cam_text}}
        
        # 3. Generate Docs
        from services.cam_generator import generate_cam_document
        docx_bytes = generate_cam_document(application_id, cam_content, "docx")
        pdf_bytes = generate_cam_document(application_id, cam_content, "pdf")
        
        # Ensure bucket exists
        try:
            supabase.storage.get_bucket("documents")
        except Exception:
            try:
                supabase.storage.create_bucket("documents", {"public": True})
            except Exception:
                pass
                
        # 4. Upload to storage
        docx_path = f"cam/{application_id}/{cam_id}.docx"
        supabase.storage.from_("documents").upload(docx_path, docx_bytes)
        docx_url = supabase.storage.from_("documents").get_public_url(docx_path)
        
        pdf_path = f"cam/{application_id}/{cam_id}.pdf"
        supabase.storage.from_("documents").upload(pdf_path, pdf_bytes)
        pdf_url = supabase.storage.from_("documents").get_public_url(pdf_path)
        
        # 5. Mark as completed
        supabase.table("cam_documents").update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "cam_content": cam_content,
            "cam_docx_url": docx_url,
            "cam_pdf_url": pdf_url,
        }).eq("id", cam_id).execute()
        
    except Exception as e:
        print(f"[ERROR] CAM writing failed: {str(e)}")
        try:
            supabase = get_supabase()
            supabase.table("cam_documents").update({
                "status": "failed",
                "error": str(e),
            }).eq("id", cam_id).execute()
        except Exception:
            pass


@router.get("/{application_id}", response_model=APIResponse)
async def get_cam(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Get CAM document(s) for an application."""
    try:
        supabase = get_supabase()
        result = supabase.table("cam_documents").select("*").eq(
            "application_id", application_id
        ).order("created_at", desc=True).execute()
        
        return APIResponse(success=True, data=result.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}/download", response_model=None)
async def download_cam(
    application_id: str,
    format: str = "docx",
    user: UserContext = Depends(get_current_user),
):
    """
    Download CAM as Word (.docx) or PDF.
    """
    try:
        supabase = get_supabase()
        
        # Get latest CAM
        result = supabase.table("cam_documents").select("*").eq(
            "application_id", application_id
        ).eq("status", "completed").order("created_at", desc=True).limit(1).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="No completed CAM found")
        
        cam = result.data[0]
        
        # Check if file URL exists
        file_key = f"cam_{format}_url"
        if cam.get(file_key):
            # Redirect to Supabase Storage URL
            return APIResponse(
                success=True,
                data={"download_url": cam[file_key], "format": format}
            )
        
        # Generate on-the-fly if not pre-generated
        from services.cam_generator import generate_cam_document
        
        file_bytes = generate_cam_document(
            application_id=application_id,
            cam_content=cam.get("cam_content", {}),
            format=format,
        )
        
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if format == "docx"
            else "application/pdf"
        )
        
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=CAM_{application_id}.{format}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{cam_id}/content", response_model=APIResponse)
async def update_cam_content(
    cam_id: str,
    content: dict,
    user: UserContext = Depends(require_analyst),
):
    """
    Update CAM content (analyst edits the AI-generated CAM).
    """
    try:
        supabase = get_supabase()
        supabase.table("cam_documents").update({
            "cam_content": content,
            "last_edited_by": user.uid,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", cam_id).execute()
        
        return APIResponse(success=True, message="CAM content updated")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
