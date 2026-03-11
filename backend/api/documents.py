"""
Document Upload & Management API Endpoints
Stage 1 — Smart document upload + background parsing.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from schemas.documents import (
    DocumentUploadRequest, DocumentRecord, DocumentChecklist,
    DocumentVerificationRequest, DocumentCompletenessResponse, CrossValidationResult
)
from schemas.common import APIResponse, DocumentStatus, LoanType
from middleware.auth import get_current_user, require_rm, UserContext
from services.supabase_client import get_supabase
from typing import List, Optional
import uuid
from datetime import datetime
import os
import tempfile

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload", response_model=APIResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    application_id: str = Form(...),
    document_type: str = Form(...),
    financial_year: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: UserContext = Depends(get_current_user),
):
    """
    Upload a document to Supabase Storage and trigger background parsing.
    """
    try:
        supabase = get_supabase()
        doc_id = str(uuid.uuid4())
        
        # Verify app exists
        app_check = supabase.table("loan_applications").select("id").eq("id", application_id).execute()
        if not app_check.data:
            raise HTTPException(status_code=404, detail="Application not found")

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Ensure bucket exists
        try:
            supabase.storage.get_bucket("documents")
        except Exception:
            try:
                supabase.storage.create_bucket("documents", {"public": True})
            except Exception:
                pass # Bucket might exist

        # Upload to Supabase Storage
        storage_path = f"documents/{application_id}/{doc_id}/{file.filename}"
        
        res = supabase.storage.from_("documents").upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )
        
        # Get public URL
        file_url = supabase.storage.from_("documents").get_public_url(storage_path)
        
        # Insert document record
        doc_record = {
            "id": doc_id,
            "application_id": application_id,
            "document_type": document_type,
            "file_name": file.filename,
            "file_url": file_url,
            "file_size": file_size,
            "mime_type": file.content_type,
            "status": DocumentStatus.UPLOADED.value,
            "financial_year": financial_year,
            "uploaded_by": user.uid,
        }
        
        db_res = supabase.table("documents").insert(doc_record).execute()
        
        # Trigger background parsing
        background_tasks.add_task(trigger_document_parsing, doc_id, storage_path, document_type)
        
        return APIResponse(
            success=True,
            message="Document uploaded successfully. Parsing started.",
            data={"document_id": doc_id, "status": "uploaded"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Document upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")


async def trigger_document_parsing(doc_id: str, storage_path: str, document_type: str):
    """Background task: Parse uploaded document using appropriate parser."""
    tmp_path = None
    try:
        supabase = get_supabase()
        
        # Update status to parsing
        supabase.table("documents").update({
            "status": DocumentStatus.PARSING.value
        }).eq("id", doc_id).execute()
        
        # Get application_id
        doc_record = supabase.table("documents").select("application_id").eq("id", doc_id).single().execute().data
        if not doc_record:
            raise Exception("Document record not found")
        app_id = doc_record["application_id"]
        
        # Download file to temp location
        res = supabase.storage.from_("documents").download(storage_path)
        tmp_path = os.path.join(tempfile.gettempdir(), f"{doc_id}.pdf")
        with open(tmp_path, "wb") as f:
            f.write(res)
            
        # Route to appropriate parser based on document_type
        doc_type_lower = document_type.lower()
        if document_type in ["Balance Sheet", "Profit & Loss Statement", "Cash Flow Statement", "Audit Report"]:
            from parsers.financial_parser import parse_financial_document
            await parse_financial_document(tmp_path, app_id, document_id=doc_id)
            
        elif "GSTR" in document_type:
            from parsers.gst_parser import parse_gst_returns
            rtype = "gstr3b" if "3B" in document_type else "gstr1"
            await parse_gst_returns([{"file_path": tmp_path, "return_type": rtype, "document_id": doc_id}], app_id)
            
        elif "Bank" in document_type or ("Statement" in document_type and "Account" in document_type):
            from parsers.banking_parser import parse_bank_statements
            await parse_bank_statements(tmp_path, app_id, document_id=doc_id)
            
        elif any(k in doc_type_lower for k in ["title deed", "valuation", "encumbrance", "cersai", "insurance"]):
            from parsers.collateral_parser import parse_collateral_document
            c_type = "title_deed"
            if "valuation" in doc_type_lower: c_type = "valuation_report"
            elif "encumbrance" in doc_type_lower: c_type = "encumbrance_certificate"
            elif "cersai" in doc_type_lower: c_type = "cersai_report"
            elif "insurance" in doc_type_lower: c_type = "insurance_policy"
            await parse_collateral_document(tmp_path, app_id, c_type, document_id=doc_id)
            
        elif any(k in doc_type_lower for k in ["shareholding", "board", "minutes", "sanction", "rating"]):
            from parsers.miscellaneous_parser import parse_miscellaneous_document
            m_type = "sanction_letter_existing"
            if "shareholding" in doc_type_lower: m_type = "shareholding_pattern"
            elif "board" in doc_type_lower or "minutes" in doc_type_lower: m_type = "board_meeting_minutes"
            elif "rating" in doc_type_lower: m_type = "rating_report"
            await parse_miscellaneous_document(tmp_path, app_id, m_type, document_id=doc_id)
            
        else:
            # Maybe KYC or other parsers if needed
            print(f"[documents API] Unhandled document type for parsing: {document_type}")
            pass
        
        # Mark as parsed
        supabase.table("documents").update({
            "status": DocumentStatus.PARSED.value,
            "parsed_at": datetime.utcnow().isoformat(),
        }).eq("id", doc_id).execute()
        
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    except Exception as e:
        try:
            supabase = get_supabase()
            supabase.table("documents").update({
                "status": DocumentStatus.EXTRACTION_FAILED.value,
                "parsing_error": str(e),
            }).eq("id", doc_id).execute()
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)


@router.get("/{application_id}", response_model=APIResponse)
async def get_application_documents(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Get all documents for an application."""
    try:
        supabase = get_supabase()
        result = supabase.table("documents").select("*").eq(
            "application_id", application_id
        ).order("created_at", desc=False).execute()
        
        return APIResponse(success=True, data=result.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/status", response_model=APIResponse)
async def get_document_status(
    document_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Get parsing status of a specific document."""
    try:
        supabase = get_supabase()
        result = supabase.table("documents").select(
            "id, status, extraction_confidence, parsing_error, parsed_at"
        ).eq("id", document_id).single().execute()
        
        return APIResponse(success=True, data=result.data)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Document not found")


@router.delete("/{document_id}", response_model=APIResponse)
async def delete_document(
    document_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Delete a document from storage and database."""
    try:
        supabase = get_supabase()
        
        # 1. Get document details to find the storage path
        doc_result = supabase.table("documents").select(
            "application_id, file_name"
        ).eq("id", document_id).single().execute()
        
        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
            
        app_id = doc_result.data["application_id"]
        file_name = doc_result.data["file_name"]
        
        # 2. Delete from storage (documents/application_id/document_id/filename)
        storage_path = f"documents/{app_id}/{document_id}/{file_name}"
        supabase.storage.from_("documents").remove([storage_path])
        
        # 3. Delete from database
        supabase.table("documents").delete().eq("id", document_id).execute()
        
        return APIResponse(success=True, message="Document deleted successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{application_id}/completeness", response_model=APIResponse)
async def get_document_completeness(
    application_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Get document upload completeness for an application."""
    try:
        supabase = get_supabase()
        
        # Get application loan type
        app = supabase.table("loan_applications").select(
            "loan_type"
        ).eq("id", application_id).single().execute()
        loan_type = app.data["loan_type"]
        
        # Get document checklist from config
        checklist_result = supabase.table("loan_type_config").select(
            "required_documents"
        ).eq("loan_type", loan_type).execute()
        
        required_docs = []
        if checklist_result.data:
            required_docs = checklist_result.data[0].get("required_documents", [])
        
        # Get uploaded documents
        docs = supabase.table("documents").select("*").eq(
            "application_id", application_id
        ).execute()
        
        uploaded_types = {d["document_type"] for d in docs.data} if docs.data else set()
        parsed_count = sum(1 for d in (docs.data or []) if d["status"] == "parsed")
        verified_count = sum(1 for d in (docs.data or []) if d["status"] == "verified")
        
        required_types = [r.get("type", r) if isinstance(r, dict) else r for r in required_docs]
        missing = [t for t in required_types if t not in uploaded_types]
        
        total_required = len(required_types) if required_types else 1
        completeness = (len(uploaded_types) / total_required) * 100 if total_required > 0 else 0
        
        return APIResponse(
            success=True,
            data=DocumentCompletenessResponse(
                application_id=application_id,
                loan_type=LoanType(loan_type),
                total_required=len(required_types),
                total_uploaded=len(uploaded_types),
                total_parsed=parsed_count,
                total_verified=verified_count,
                completeness_percent=min(completeness, 100),
                missing_documents=missing,
                documents=[DocumentRecord(**d) for d in (docs.data or [])],
            ).model_dump()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_model=APIResponse)
async def verify_document(
    request: DocumentVerificationRequest,
    user: UserContext = Depends(require_rm),
):
    """RM verifies/rejects a document."""
    try:
        supabase = get_supabase()
        
        status_map = {
            "verify": DocumentStatus.VERIFIED.value,
            "reject": DocumentStatus.REJECTED.value,
            "request_reupload": DocumentStatus.REJECTED.value,
        }
        
        supabase.table("documents").update({
            "status": status_map.get(request.action, "verified"),
            "verified_by": user.uid,
            "verified_at": datetime.utcnow().isoformat(),
            "verification_remarks": request.remarks,
        }).eq("id", request.document_id).execute()
        
        # Log audit
        supabase.table("audit_logs").insert({
            "id": str(uuid.uuid4()),
            "entity_type": "document",
            "entity_id": request.document_id,
            "action": f"document_{request.action}",
            "performed_by": user.uid,
            "details": {"remarks": request.remarks},
        }).execute()
        
        return APIResponse(success=True, message=f"Document {request.action} successful")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checklist/{loan_type}", response_model=APIResponse)
async def get_document_checklist(
    loan_type: str,
    user: UserContext = Depends(get_current_user),
):
    """Get required document checklist for a loan type (from config table)."""
    try:
        supabase = get_supabase()
        result = supabase.table("loan_type_config").select("*").eq(
            "loan_type", loan_type
        ).execute()
        
        if not result.data:
            return APIResponse(success=True, data={"required_documents": []})
        
        return APIResponse(success=True, data=result.data[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
