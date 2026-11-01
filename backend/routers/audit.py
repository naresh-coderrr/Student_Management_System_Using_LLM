"""Audit log router."""

from fastapi import APIRouter, Query

from services.supabase_service import supabase_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/")
async def list_audit(limit: int = Query(40, ge=1, le=200)):
    """Recent changes, including assistant actions and the rows they replaced."""
    rows = supabase_service.get_audit_log(limit=limit)
    return rows if isinstance(rows, list) else []
