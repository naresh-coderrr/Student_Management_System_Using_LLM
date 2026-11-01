"""Table structure.

Viva: there is no fixed students table. The user names the table and each column,
picks a data type, and marks the primary key. This file turns that form into CREATE or ALTER.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.supabase_service import supabase_service

router = APIRouter(prefix="/api/tables", tags=["tables"])

# ── Allowed data types ────────────────────────────────────────────────

ALLOWED_DATA_TYPES = {
    "TEXT", "INTEGER", "BIGINT", "SERIAL", "BIGSERIAL",
    "BOOLEAN", "DATE", "TIMESTAMP", "TIMESTAMPTZ",
    "NUMERIC", "REAL", "DOUBLE PRECISION",
    "JSON", "JSONB", "UUID",
}
# VARCHAR(n) is also allowed – matched dynamically
VARCHAR_PATTERN = re.compile(r"^VARCHAR\(\d+\)$", re.IGNORECASE)

TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_table_name(name: str) -> None:
    if not TABLE_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid table name. Use only letters, digits, and underscores; must start with a letter or underscore.",
        )


def _validate_data_type(dt: str) -> None:
    upper = dt.upper().strip()
    if upper in ALLOWED_DATA_TYPES:
        return
    if VARCHAR_PATTERN.match(upper):
        return
    raise HTTPException(status_code=400, detail=f"Unsupported data type: {dt}")


def _quote_ident(name: str) -> str:
    """Return a safely double-quoted SQL identifier."""
    return '"' + name.replace('"', '""') + '"'


# ── Request / response models ────────────────────────────────────────

class ColumnDefinition(BaseModel):
    name: str
    data_type: str
    is_primary_key: bool = False
    is_nullable: bool = True
    is_unique: bool = False
    default_value: Optional[str] = None


class CreateTableRequest(BaseModel):
    table_name: str
    columns: List[ColumnDefinition]


class AlterTableRequest(BaseModel):
    operation: str  # rename_table | add_column | drop_column | rename_column | alter_column_type
    # Fields used depending on operation:
    new_table_name: Optional[str] = None
    column: Optional[ColumnDefinition] = None
    column_name: Optional[str] = None
    new_column_name: Optional[str] = None
    new_data_type: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/")
async def list_tables():
    """List all user-created tables with columns and row counts."""
    try:
        tables = supabase_service.get_tables()
        result: list[dict[str, Any]] = []
        for tbl in tables:
            name = tbl.get("table_name", tbl) if isinstance(tbl, dict) else tbl
            columns = supabase_service.get_columns(name)
            row_count = supabase_service.get_row_count(name)
            result.append({
                "table_name": name,
                "columns": columns,
                "row_count": row_count,
            })
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/")
async def create_table(body: CreateTableRequest):
    """Create a new table."""
    _validate_table_name(body.table_name)

    if not body.columns:
        raise HTTPException(status_code=400, detail="At least one column is required.")

    col_defs: list[str] = []
    for col in body.columns:
        _validate_data_type(col.data_type)
        parts = [_quote_ident(col.name), col.data_type.upper()]
        if col.is_primary_key:
            parts.append("PRIMARY KEY")
        if not col.is_nullable and not col.is_primary_key:
            parts.append("NOT NULL")
        if col.is_unique and not col.is_primary_key:
            parts.append("UNIQUE")
        if col.default_value is not None:
            parts.append(f"DEFAULT {col.default_value}")
        col_defs.append(" ".join(parts))

    sql = f"CREATE TABLE {_quote_ident(body.table_name)} ({', '.join(col_defs)});"

    result = supabase_service.execute_sql(sql)
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create table"))

    supabase_service.log_audit(
        table_name=body.table_name,
        action="CREATE_TABLE",
        new_data={"columns": [c.model_dump() for c in body.columns]},
        sql_query=sql,
        description=f"Created table {body.table_name} with {len(body.columns)} columns",
    )

    return {"message": f"Table '{body.table_name}' created successfully", "sql": sql}


@router.get("/{name}")
async def get_table_schema(name: str):
    """Return the column schema for a specific table."""
    _validate_table_name(name)
    if not supabase_service.validate_table_exists(name):
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")

    columns = supabase_service.get_columns(name)
    return {"table_name": name, "columns": columns}


@router.put("/{name}")
async def alter_table(name: str, body: AlterTableRequest):
    """Alter an existing table (rename, add/drop/rename column, change type)."""
    _validate_table_name(name)
    if not supabase_service.validate_table_exists(name):
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")

    sql = ""
    description = ""
    op = body.operation.lower()

    if op == "rename_table":
        if not body.new_table_name:
            raise HTTPException(status_code=400, detail="new_table_name is required")
        _validate_table_name(body.new_table_name)
        sql = f"ALTER TABLE {_quote_ident(name)} RENAME TO {_quote_ident(body.new_table_name)};"
        description = f"Renamed table {name} to {body.new_table_name}"

    elif op == "add_column":
        if not body.column:
            raise HTTPException(status_code=400, detail="column definition is required")
        _validate_data_type(body.column.data_type)
        col_parts = [_quote_ident(body.column.name), body.column.data_type.upper()]
        if not body.column.is_nullable:
            col_parts.append("NOT NULL")
        if body.column.is_unique:
            col_parts.append("UNIQUE")
        if body.column.default_value is not None:
            col_parts.append(f"DEFAULT {body.column.default_value}")
        sql = f"ALTER TABLE {_quote_ident(name)} ADD COLUMN {' '.join(col_parts)};"
        description = f"Added column {body.column.name} to {name}"

    elif op == "drop_column":
        if not body.column_name:
            raise HTTPException(status_code=400, detail="column_name is required")
        sql = f"ALTER TABLE {_quote_ident(name)} DROP COLUMN {_quote_ident(body.column_name)};"
        description = f"Dropped column {body.column_name} from {name}"

    elif op == "rename_column":
        if not body.column_name or not body.new_column_name:
            raise HTTPException(status_code=400, detail="column_name and new_column_name are required")
        sql = (
            f"ALTER TABLE {_quote_ident(name)} "
            f"RENAME COLUMN {_quote_ident(body.column_name)} TO {_quote_ident(body.new_column_name)};"
        )
        description = f"Renamed column {body.column_name} to {body.new_column_name} in {name}"

    elif op == "alter_column_type":
        if not body.column_name or not body.new_data_type:
            raise HTTPException(status_code=400, detail="column_name and new_data_type are required")
        _validate_data_type(body.new_data_type)
        sql = (
            f"ALTER TABLE {_quote_ident(name)} "
            f"ALTER COLUMN {_quote_ident(body.column_name)} TYPE {body.new_data_type.upper()};"
        )
        description = f"Changed type of {body.column_name} to {body.new_data_type} in {name}"

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported operation: {body.operation}. "
                   "Supported: rename_table, add_column, drop_column, rename_column, alter_column_type",
        )

    result = supabase_service.execute_sql(sql)
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to alter table"))

    supabase_service.log_audit(
        table_name=name,
        action="ALTER_TABLE",
        new_data=body.model_dump(),
        sql_query=sql,
        description=description,
    )

    return {"message": description, "sql": sql}


@router.delete("/{name}")
async def drop_table(name: str):
    """Drop a table."""
    _validate_table_name(name)
    if not supabase_service.validate_table_exists(name):
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")

    # Capture schema before drop for the audit log
    old_columns = supabase_service.get_columns(name)

    sql = f"DROP TABLE {_quote_ident(name)} CASCADE;"
    result = supabase_service.execute_sql(sql)
    if isinstance(result, dict) and result.get("success") is False:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to drop table"))

    supabase_service.log_audit(
        table_name=name,
        action="DROP_TABLE",
        old_data={"columns": old_columns},
        sql_query=sql,
        description=f"Dropped table {name}",
    )

    return {"message": f"Table '{name}' dropped successfully"}


@router.get("/{name}/stats")
async def get_table_stats(name: str):
    """Return row count and column count for a table."""
    _validate_table_name(name)
    if not supabase_service.validate_table_exists(name):
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")

    columns = supabase_service.get_columns(name)
    row_count = supabase_service.get_row_count(name)

    return {
        "table_name": name,
        "row_count": row_count,
        "column_count": len(columns),
    }
