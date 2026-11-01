"""Chatbot routes.

Viva, in this order:
1. /chat sends the user's sentence plus the current table list to Gemini.
2. If the SQL only reads data, it runs now.
3. If the SQL changes data, it is stored in pending_actions and not run.
4. For update or delete, a SELECT loads the current row and that row is shown.
5. /confirm checks the user's password, then runs the stored SQL on Supabase.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from supabase import create_client

from config import get_settings
from services.supabase_service import supabase_service
from services.llm_service import llm_service
from services.rag_service import rag_service

router = APIRouter(prefix="/api/llm", tags=["llm"])

# Module-level store of pending actions awaiting user confirmation
pending_actions: dict[str, dict] = {}


# ── Request models ────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []


class ConfirmRequest(BaseModel):
    action_id: str
    confirmed: bool
    password: str = ""


READ_PREFIXES = ("SELECT", "WITH", "SHOW", "EXPLAIN")
WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TRUNCATE")


def _statement(sql: str) -> str:
    text = sql.strip()
    text = re.sub(r"^/\*.*?\*/", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^--.*?$", "", text, flags=re.MULTILINE).strip()
    return text


def _is_single_statement(sql: str) -> bool:
    body = sql.strip().rstrip(";").strip()
    return ";" not in body


def _leading_keyword(sql: str) -> str:
    match = re.match(r"([A-Za-z]+)", _statement(sql))
    return match.group(1).upper() if match else ""


def _is_write(sql: str) -> bool:
    return _leading_keyword(sql) in WRITE_PREFIXES


def _preview_select(sql: str) -> str | None:
    """Turn an UPDATE or DELETE into a SELECT of the rows that would change."""
    text = _statement(sql).rstrip(";").strip()
    updated = re.match(
        r"UPDATE\s+(.+?)\s+SET\s+.+?\s+WHERE\s+(.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if updated:
        return f"SELECT * FROM {updated.group(1)} WHERE {updated.group(2)}"
    deleted = re.match(
        r"DELETE\s+FROM\s+(.+?)\s+WHERE\s+(.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if deleted:
        return f"SELECT * FROM {deleted.group(1)} WHERE {deleted.group(2)}"
    bare_update = re.match(r"UPDATE\s+(.+?)\s+SET\s+.+$", text, flags=re.IGNORECASE | re.DOTALL)
    if bare_update:
        return f"SELECT * FROM {bare_update.group(1)} LIMIT 25"
    bare_delete = re.match(r"DELETE\s+FROM\s+(.+)$", text, flags=re.IGNORECASE | re.DOTALL)
    if bare_delete:
        return f"SELECT * FROM {bare_delete.group(1)} LIMIT 25"
    return None


def _check_password(email: str, password: str) -> None:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_publishable_key)
    try:
        client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Password did not match. Nothing was changed.",
        )


class HelpRequest(BaseModel):
    question: str


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """Process a natural-language message about database operations.

    The LLM receives the current schema as context and returns a
    structured response. Data-modifying actions are stored as *pending*
    until the user explicitly confirms them via ``/api/llm/confirm``.
    """
    try:
        # 1. Build schema context
        schema = supabase_service.get_full_schema()
        schema_text = llm_service.format_schema_context(schema)

        # 2. Prepare conversation history
        history = [
            {"role": m.role, "content": m.content}
            for m in body.conversation_history
        ]

        # 3. Send to Gemini
        response = llm_service.generate_response(
            user_message=body.message,
            schema_context=schema_text,
            conversation_history=history,
        )

        sql = (response.get("sql") or "").strip()
        keyword = _leading_keyword(sql) if sql else ""
        if sql and not _is_single_statement(sql):
            return {
                "type": "error",
                "message": "The assistant prepared more than one SQL statement. Ask again for a single change.",
                "sql": "",
                "preview_data": [],
                "action_id": "",
            }
        if sql and keyword and keyword not in READ_PREFIXES and keyword not in WRITE_PREFIXES:
            return {
                "type": "error",
                "message": f"The statement type {keyword} is not allowed. Use a normal table or data command.",
                "sql": "",
                "preview_data": [],
                "action_id": "",
            }

        # Writes always wait for the user, even if the model forgot to ask.
        if sql and _is_write(sql):
            response["type"] = "confirm_action"
            preview_sql = _preview_select(sql)
            if preview_sql:
                fetched = supabase_service.query_sql(preview_sql)
                if isinstance(fetched, list):
                    response["preview_data"] = fetched
                    response["affects_all"] = not re.search(r"\bWHERE\b", sql, flags=re.IGNORECASE)
            action_id = str(uuid.uuid4())
            response["action_id"] = action_id
            pending_actions[action_id] = {
                "sql": sql,
                "message": response.get("message", ""),
                "preview_data": response.get("preview_data", []),
                "requested_by": getattr(request.state, "user_email", None),
            }

        # Read queries can run immediately and show their rows.
        if response.get("type") != "confirm_action" and sql and keyword in ("SELECT", "WITH"):
            try:
                query_result = supabase_service.query_sql(sql)
                if isinstance(query_result, list):
                    response["preview_data"] = query_result
                    response["type"] = "info"
            except Exception:
                pass

        return response

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM chat error: {exc}")


@router.post("/confirm")
async def confirm_action(body: ConfirmRequest, request: Request):
    """Confirm or cancel a pending change. Confirmation requires the user's password."""
    action = pending_actions.get(body.action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or already processed")

    if not body.confirmed:
        pending_actions.pop(body.action_id, None)
        return {"message": "Action cancelled. Nothing was changed.", "action_id": body.action_id}

    email = getattr(request.state, "user_email", None)
    if not email or not body.password:
        raise HTTPException(status_code=401, detail="Enter your password to approve this change.")
    _check_password(email, body.password)

    pending_actions.pop(body.action_id, None)
    sql = action["sql"]
    try:
        result = supabase_service.execute_sql(sql)
        if isinstance(result, dict) and result.get("success") is False:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "SQL execution failed"),
            )

        supabase_service.log_audit(
            table_name="llm_action",
            action="LLM_ACTION",
            new_data={
                "sql": sql,
                "message": action.get("message", ""),
                "previous_rows": action.get("preview_data", []),
            },
            executed_by=email,
            sql_query=sql,
            description=f"Approved by {email}: {action.get('message', '')}",
        )

        return {
            "message": "Action executed successfully",
            "action_id": body.action_id,
            "sql": sql,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution error: {exc}")


@router.post("/help")
async def help_endpoint(body: HelpRequest):
    """Answer a help question using RAG (retrieval-augmented generation)."""
    try:
        answer = rag_service.generate_help_response(body.question)
        return {"question": body.question, "answer": answer}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Help error: {exc}")
