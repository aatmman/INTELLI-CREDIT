"""
Supabase Client Service
Singleton Supabase client for all DB + Storage operations.
"""

from supabase import create_client, Client
from config import settings
from typing import Optional

_supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    """Get or create Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _supabase_client


def reset_supabase_client():
    """Reset client (for testing)."""
    global _supabase_client
    _supabase_client = None
