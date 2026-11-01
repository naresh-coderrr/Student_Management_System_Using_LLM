"""Rows inside a table.

Viva: add, edit, delete, search, and CSV download.
An edit loads the old row, writes the new values, and keeps both in the activity log.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.supabase_service import supabase_service

router = APIRouter(prefix="/api/records", tags=["records"])

TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_table_name(name: str) -> None:
    if not TABLE_NAME_PATTERN.match(name):
        raise HTTPException(status_code=400, detail="Invalid table name.")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _quote_literal(value: Any) -> str:
    """Return a safely single-quoted SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    # String – escape single quotes
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _ensure_table(name: str) -> None:
    _validate_table_name(name)
    if not supabase_service.validate_table_exists(name):
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")


# ── Request models ────────────────────────────────────────────────────

class InsertRecordRequest(BaseModel):
    data: Dict[str, Any]


class UpdateRecordRequest(BaseModel):
    primary_key_column: str
    primary_key_value: Any
    updates: Dict[str, Any]


class DeleteRecordRequest(BaseModel):
    primary_key_column: str
    primary_key_value: Any


class BulkInsertRequest(BaseModel):
    records: List[Dict[str, Any]]


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/{table_name}")
async def get_records(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=500),
    sort_by: Optional[str] = None,
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: Optional[str] = None,
    filters: Optional[str] = None,
):
    """Fetch paginated, sortable, filterable records from a table."""
    _ensure_table(table_name)

    tbl = _quote_ident(table_name)

    # --- WHERE clause ------------------------------------------------
    where_clauses: list[str] = []

    # Free-text search across all text-like columns
    if search:
        columns = supabase_service.get_columns(table_name)
        text_cols = [
            c.get("column_name", c.get("name", ""))
            for c in columns
            if c.get("data_type", "").upper() in (
                "TEXT", "VARCHAR", "CHARACTER VARYING", "CHAR", "CHARACTER",
            )
        ]
        if text_cols:
            or_parts = [
                f"{_quote_ident(col)}::TEXT ILIKE {_quote_literal(f'%{search}%')}"
                for col in text_cols
            ]
            where_clauses.append(f"({' OR '.join(or_parts)})")

    # Column-specific filters
    if filters:
        try:
            filter_dict = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="filters must be a valid JSON string")
        for col, val in filter_dict.items():
            where_clauses.append(
                f"{_quote_ident(col)} = {_quote_literal(val)}"
            )

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # --- Total count -------------------------------------------------
    count_sql = f"SELECT COUNT(*) AS cnt FROM {tbl}{where_sql};"
    count_result = supabase_service.query_sql(count_sql)

    total = 0
    if isinstance(count_result, list) and count_result:
        total = count_result[0].get("cnt", 0)
    elif isinstance(count_result, dict) and "error" in count_result:
        raise HTTPException(status_code=400, detail=count_result["error"])

    total_pages = max(1, math.ceil(total / page_size))

    # --- ORDER BY ----------------------------------------------------
    order_sql = ""
    if sort_by:
        order_sql = f" ORDER BY {_quote_ident(sort_by)} {sort_order.upper()}"

    # --- LIMIT / OFFSET ----------------------------------------------
    offset = (page - 1) * page_size
    limit_sql = f" LIMIT {page_size} OFFSET {offset}"

    # --- Execute query -----------------------------------------------
    select_sql = f"SELECT * FROM {tbl}{where_sql}{order_sql}{limit_sql};"
    data = supabase_service.query_sql(select_sql)
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post("/{table_name}")
async def insert_record(table_name: str, body: InsertRecordRequest):
    """Insert a single record into the table."""
    _ensure_table(table_name)

    if not body.data:
        raise HTTPException(status_code=400, detail="No data provided")

    columns = ", ".join(_quote_ident(k) for k in body.data.keys())
    values = ", ".join(_quote_literal(v) for v in body.data.values())
    sql = f"INSERT INTO {_quote_ident(table_name)} ({columns}) VALUES ({values});"

    result = supabase_service.execute_sql(sql)
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=400, detail=result.get("error", "Insert failed"))

    supabase_service.log_audit(
        table_name=table_name,
        action="INSERT",
        new_data=body.data,
        sql_query=sql,
        description=f"Inserted 1 record into {table_name}",
    )

    return {"message": "Record inserted successfully", "data": body.data}


@router.put("/{table_name}")
async def update_record(table_name: str, body: UpdateRecordRequest):
    """Update a record identified by its primary key."""
    _ensure_table(table_name)

    if not body.updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    tbl = _quote_ident(table_name)
    pk_col = _quote_ident(body.primary_key_column)
    pk_val = _quote_literal(body.primary_key_value)

    # Fetch old data
    old_sql = f"SELECT * FROM {tbl} WHERE {pk_col} = {pk_val} LIMIT 1;"
    old_data = supabase_service.query_sql(old_sql)
    if isinstance(old_data, dict) and "error" in old_data:
        raise HTTPException(status_code=400, detail=old_data["error"])
    if not old_data:
        raise HTTPException(status_code=404, detail="Record not found")

    # Build UPDATE
    set_parts = [
        f"{_quote_ident(col)} = {_quote_literal(val)}"
        for col, val in body.updates.items()
    ]
    sql = f"UPDATE {tbl} SET {', '.join(set_parts)} WHERE {pk_col} = {pk_val};"

    result = supabase_service.execute_sql(sql)
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=400, detail=result.get("error", "Update failed"))

    # Fetch new data
    new_data = supabase_service.query_sql(
        f"SELECT * FROM {tbl} WHERE {pk_col} = {pk_val} LIMIT 1;"
    )

    supabase_service.log_audit(
        table_name=table_name,
        action="UPDATE",
        old_data=old_data[0] if old_data else None,
        new_data=new_data[0] if isinstance(new_data, list) and new_data else body.updates,
        sql_query=sql,
        description=f"Updated record in {table_name} where {body.primary_key_column} = {body.primary_key_value}",
    )

    return {
        "message": "Record updated successfully",
        "old_data": old_data[0] if old_data else None,
        "new_data": new_data[0] if isinstance(new_data, list) and new_data else body.updates,
    }


@router.delete("/{table_name}")
async def delete_record(table_name: str, body: DeleteRecordRequest):
    """Delete a record identified by its primary key."""
    _ensure_table(table_name)

    tbl = _quote_ident(table_name)
    pk_col = _quote_ident(body.primary_key_column)
    pk_val = _quote_literal(body.primary_key_value)

    # Fetch old data before deleting
    old_sql = f"SELECT * FROM {tbl} WHERE {pk_col} = {pk_val} LIMIT 1;"
    old_data = supabase_service.query_sql(old_sql)
    if isinstance(old_data, dict) and "error" in old_data:
        raise HTTPException(status_code=400, detail=old_data["error"])
    if not old_data:
        raise HTTPException(status_code=404, detail="Record not found")

    sql = f"DELETE FROM {tbl} WHERE {pk_col} = {pk_val};"
    result = supabase_service.execute_sql(sql)
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=400, detail=result.get("error", "Delete failed"))

    supabase_service.log_audit(
        table_name=table_name,
        action="DELETE",
        old_data=old_data[0] if old_data else None,
        sql_query=sql,
        description=f"Deleted record from {table_name} where {body.primary_key_column} = {body.primary_key_value}",
    )

    return {"message": "Record deleted successfully", "deleted": old_data[0] if old_data else None}


@router.post("/{table_name}/bulk")
async def bulk_insert(table_name: str, body: BulkInsertRequest):
    """Insert multiple records at once."""
    _ensure_table(table_name)

    if not body.records:
        raise HTTPException(status_code=400, detail="No records provided")

    # Use the keys of the first record to define column order
    columns = list(body.records[0].keys())
    col_str = ", ".join(_quote_ident(c) for c in columns)

    value_rows: list[str] = []
    for record in body.records:
        vals = ", ".join(_quote_literal(record.get(c)) for c in columns)
        value_rows.append(f"({vals})")

    sql = f"INSERT INTO {_quote_ident(table_name)} ({col_str}) VALUES {', '.join(value_rows)};"

    result = supabase_service.execute_sql(sql)
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=400, detail=result.get("error", "Bulk insert failed"))

    supabase_service.log_audit(
        table_name=table_name,
        action="BULK_INSERT",
        new_data={"count": len(body.records)},
        sql_query=sql,
        description=f"Bulk inserted {len(body.records)} records into {table_name}",
    )

    return {"message": f"Successfully inserted {len(body.records)} records", "count": len(body.records)}


@router.post("/{table_name}/export")
async def export_csv(table_name: str):
    """Export all records of a table as a CSV download."""
    _ensure_table(table_name)

    sql = f"SELECT * FROM {_quote_ident(table_name)};"
    data = supabase_service.query_sql(sql)
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])

    if not data:
        return StreamingResponse(
            io.StringIO(""),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
    )
