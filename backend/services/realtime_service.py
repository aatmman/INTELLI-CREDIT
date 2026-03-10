"""
Supabase Realtime Service
Broadcasts agent progress updates to frontend via Supabase Realtime.
"""

from services.supabase_client import get_supabase
from typing import Any, Dict, Optional
from datetime import datetime


async def broadcast_agent_progress(
    application_id: str,
    agent_name: str,
    status: str,
    progress_percent: float = 0,
    message: str = "",
    data: Optional[Dict[str, Any]] = None,
):
    """
    Broadcast agent progress to frontend via Supabase Realtime.
    
    Updates a row in a 'agent_progress' table that the frontend
    subscribes to via Supabase Realtime channels.
    """
    try:
        supabase = get_supabase()
        
        progress_record = {
            "application_id": application_id,
            "agent_name": agent_name,
            "status": status,  # running | completed | failed
            "progress_percent": progress_percent,
            "message": message,
            "data": data or {},
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Upsert to enable real-time subscription on frontend
        supabase.table("agent_progress").upsert(
            progress_record,
            on_conflict="application_id,agent_name"
        ).execute()
        
    except Exception as e:
        print(f"[WARNING] Realtime broadcast failed: {e}")


async def update_stage_progress(
    application_id: str,
    stage: str,
    step: str,
    total_steps: int,
    current_step: int,
):
    """Broadcast stage-level progress."""
    await broadcast_agent_progress(
        application_id=application_id,
        agent_name=f"stage_{stage}",
        status="running",
        progress_percent=(current_step / max(total_steps, 1)) * 100,
        message=step,
    )
