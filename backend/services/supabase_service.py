"""The only place that talks to the Supabase database.

Viva: execute_sql runs CREATE, ALTER, INSERT, UPDATE, DELETE through the exec_sql function.
query_sql runs SELECT through exec_sql_query.
Both functions are created by setup.sql. A trailing semicolon is removed so PostgreSQL
does not report "syntax error at or near ;".
"""

from __future__ import annotations

from typing import Any

from database import supabase_admin

SETUP_HINT = (
    "Supabase is missing the registry functions. Open your project, go to SQL Editor, "
    "paste the contents of backend/setup.sql, run it once, then approve the change again."
)


def _explain(exc: Exception) -> str:
    text = str(exc)
    if "PGRST202" in text or "Could not find the function" in text:
        return SETUP_HINT
    return text


class SupabaseService:
    """Thin convenience layer over Supabase RPC calls."""

    # ------------------------------------------------------------------
    # SQL execution
    # ------------------------------------------------------------------

    @staticmethod
    def execute_sql(sql: str) -> dict:
        """Execute a DDL / DML statement via the ``exec_sql`` RPC.

        Returns ``{"success": True}`` or ``{"success": False, "error": "..."}``
        """
        try:
            cleaned = sql.strip().rstrip(";").strip()
            response = supabase_admin.rpc("exec_sql", {"query": cleaned}).execute()
            return response.data if response.data else {"success": True}
        except Exception as exc:
            return {"success": False, "error": _explain(exc)}

    @staticmethod
    def query_sql(sql: str) -> list | dict:
        """Execute a SELECT-style query via ``exec_sql_query`` RPC.

        Returns a JSON array of rows or ``{"error": "..."}``.
        """
        try:
            cleaned = sql.strip().rstrip(";").strip()
            response = supabase_admin.rpc("exec_sql_query", {"query": cleaned}).execute()
            return response.data if response.data else []
        except Exception as exc:
            return {"error": _explain(exc)}

    # ------------------------------------------------------------------
    # Table introspection
    # ------------------------------------------------------------------

    @staticmethod
    def get_tables() -> list:
        """Return the list of user-created tables."""
        try:
            response = supabase_admin.rpc("get_user_tables").execute()
            return response.data if response.data else []
        except Exception as exc:
            raise RuntimeError(_explain(exc)) from exc

    @staticmethod
    def get_columns(table_name: str) -> list:
        """Return column metadata for *table_name*."""
        try:
            response = supabase_admin.rpc(
                "get_table_columns", {"target_table": table_name}
            ).execute()
            return response.data if response.data else []
        except Exception as exc:
            return []

    @staticmethod
    def get_row_count(table_name: str) -> int:
        """Return the row count for *table_name*."""
        try:
            response = supabase_admin.rpc(
                "get_table_row_count", {"target_table": table_name}
            ).execute()
            if response.data and isinstance(response.data, dict):
                return response.data.get("count", 0)
            if response.data and isinstance(response.data, list) and len(response.data) > 0:
                return response.data[0].get("count", 0)
            return 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    @staticmethod
    def log_audit(
        table_name: str,
        action: str,
        old_data: Any = None,
        new_data: Any = None,
        executed_by: str = "system",
        sql_query: str = "",
        description: str = "",
    ) -> dict:
        """Write an entry to the audit log via ``log_audit`` RPC."""
        import json

        try:
            response = supabase_admin.rpc(
                "log_audit",
                {
                    "p_table_name": table_name,
                    "p_action": action,
                    "p_old_data": json.dumps(old_data) if old_data else None,
                    "p_new_data": json.dumps(new_data) if new_data else None,
                    "p_executed_by": executed_by,
                    "p_sql_query": sql_query,
                    "p_description": description,
                },
            ).execute()
            return response.data if response.data else {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_audit_log(
        table_name: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        """Fetch audit log entries."""
        try:
            response = supabase_admin.rpc(
                "get_audit_log",
                {
                    "p_table_name": table_name,
                    "p_action": action,
                    "p_limit": limit,
                    "p_offset": offset,
                },
            ).execute()
            return response.data if response.data else []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_full_schema() -> dict:
        """Build a complete schema dict: ``{table_name: {columns: [...], row_count: N}}``."""
        tables = SupabaseService.get_tables()
        schema: dict[str, Any] = {}
        for tbl in tables:
            name = tbl.get("table_name", tbl) if isinstance(tbl, dict) else tbl
            columns = SupabaseService.get_columns(name)
            row_count = SupabaseService.get_row_count(name)
            schema[name] = {"columns": columns, "row_count": row_count}
        return schema

    @staticmethod
    def validate_table_exists(table_name: str) -> bool:
        """Return ``True`` if *table_name* exists among the user tables."""
        tables = SupabaseService.get_tables()
        for tbl in tables:
            name = tbl.get("table_name", tbl) if isinstance(tbl, dict) else tbl
            if name == table_name:
                return True
        return False


# Module-level singleton for convenience
supabase_service = SupabaseService()
