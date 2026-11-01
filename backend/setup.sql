-- ============================================================
-- Student Management System - Supabase Setup Script
-- Run this ONCE in your Supabase SQL Editor (Dashboard > SQL Editor)
-- ============================================================

-- 1. Function to execute DDL/DML SQL statements (CREATE, ALTER, DROP, INSERT, UPDATE, DELETE)
CREATE OR REPLACE FUNCTION exec_sql(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    EXECUTE query;
    RETURN json_build_object('success', true);
EXCEPTION WHEN OTHERS THEN
    RETURN json_build_object('success', false, 'error', SQLERRM, 'detail', SQLSTATE);
END;
$$;

-- 2. Function to execute SELECT queries and return JSON results
CREATE OR REPLACE FUNCTION exec_sql_query(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result json;
BEGIN
    EXECUTE 'SELECT COALESCE(json_agg(row_to_json(t)), ''[]''::json) FROM (' || query || ') t' INTO result;
    RETURN result;
EXCEPTION WHEN OTHERS THEN
    RETURN json_build_object('error', SQLERRM, 'detail', SQLSTATE);
END;
$$;

-- 3. Function to list all user-created tables in the public schema
CREATE OR REPLACE FUNCTION get_user_tables()
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result json;
BEGIN
    SELECT COALESCE(json_agg(json_build_object(
        'table_name', t.table_name,
        'table_schema', t.table_schema
    )), '[]'::json)
    FROM information_schema.tables t
    WHERE t.table_schema = 'public'
      AND t.table_type = 'BASE TABLE'
      AND t.table_name NOT LIKE 'pg_%'
      AND t.table_name NOT IN ('schema_migrations', 'audit_log')
    INTO result;
    RETURN result;
END;
$$;

-- 4. Function to get column details for a specific table
CREATE OR REPLACE FUNCTION get_table_columns(target_table text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result json;
BEGIN
    SELECT COALESCE(json_agg(json_build_object(
        'column_name', c.column_name,
        'data_type', c.data_type,
        'udt_name', c.udt_name,
        'is_nullable', c.is_nullable,
        'column_default', c.column_default,
        'character_maximum_length', c.character_maximum_length,
        'numeric_precision', c.numeric_precision,
        'ordinal_position', c.ordinal_position,
        'is_primary_key', CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END,
        'is_unique', CASE WHEN uq.column_name IS NOT NULL THEN true ELSE false END
    ) ORDER BY c.ordinal_position), '[]'::json)
    FROM information_schema.columns c
    LEFT JOIN (
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = target_table AND tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY'
    ) pk ON c.column_name = pk.column_name
    LEFT JOIN (
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = target_table AND tc.table_schema = 'public' AND tc.constraint_type = 'UNIQUE'
    ) uq ON c.column_name = uq.column_name
    WHERE c.table_name = target_table AND c.table_schema = 'public'
    INTO result;
    RETURN result;
END;
$$;

-- 5. Function to get row count for a table
CREATE OR REPLACE FUNCTION get_table_row_count(target_table text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    row_count bigint;
BEGIN
    EXECUTE 'SELECT COUNT(*) FROM ' || quote_ident(target_table) INTO row_count;
    RETURN json_build_object('count', row_count);
EXCEPTION WHEN OTHERS THEN
    RETURN json_build_object('error', SQLERRM);
END;
$$;

-- 6. Audit log table for tracking all changes
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('CREATE_TABLE', 'ALTER_TABLE', 'DROP_TABLE', 'INSERT', 'UPDATE', 'DELETE', 'BULK_INSERT', 'LLM_ACTION')),
    old_data JSONB,
    new_data JSONB,
    executed_by TEXT DEFAULT 'system',
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    sql_query TEXT,
    description TEXT
);

-- Index for faster audit log queries
CREATE INDEX IF NOT EXISTS idx_audit_log_table ON audit_log(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_date ON audit_log(executed_at DESC);

-- 7. Function to insert audit log entries
CREATE OR REPLACE FUNCTION log_audit(
    p_table_name text,
    p_action text,
    p_old_data jsonb DEFAULT NULL,
    p_new_data jsonb DEFAULT NULL,
    p_executed_by text DEFAULT 'system',
    p_sql_query text DEFAULT NULL,
    p_description text DEFAULT NULL
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO audit_log (table_name, action, old_data, new_data, executed_by, sql_query, description)
    VALUES (p_table_name, p_action, p_old_data, p_new_data, p_executed_by, p_sql_query, p_description);
    RETURN json_build_object('success', true);
END;
$$;

-- 8. Function to get audit log entries with optional filters
CREATE OR REPLACE FUNCTION get_audit_log(
    p_table_name text DEFAULT NULL,
    p_action text DEFAULT NULL,
    p_limit integer DEFAULT 50,
    p_offset integer DEFAULT 0
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    result json;
    query text;
BEGIN
    query := 'SELECT id, table_name, action, old_data, new_data, executed_by, executed_at, sql_query, description FROM audit_log WHERE 1=1';
    IF p_table_name IS NOT NULL THEN
        query := query || ' AND table_name = ' || quote_literal(p_table_name);
    END IF;
    IF p_action IS NOT NULL THEN
        query := query || ' AND action = ' || quote_literal(p_action);
    END IF;
    query := query || ' ORDER BY executed_at DESC LIMIT ' || p_limit || ' OFFSET ' || p_offset;
    EXECUTE 'SELECT COALESCE(json_agg(row_to_json(t)), ''[]''::json) FROM (' || query || ') t' INTO result;
    RETURN result;
END;
$$;

-- 9. Grant execute permissions to authenticated and anon roles
GRANT EXECUTE ON FUNCTION exec_sql(text) TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION exec_sql_query(text) TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION get_user_tables() TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION get_table_columns(text) TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION get_table_row_count(text) TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION log_audit(text, text, jsonb, jsonb, text, text, text) TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION get_audit_log(text, text, integer, integer) TO authenticated, anon, service_role;

-- Enable RLS on audit_log but allow all access for authenticated users
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for authenticated" ON audit_log FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON audit_log FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service_role" ON audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Done!
NOTIFY pgrst, 'reload schema';
SELECT 'Setup complete! All functions and tables created successfully.' as status;
