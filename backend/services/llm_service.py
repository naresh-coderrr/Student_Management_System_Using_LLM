"""Ask Gemini to turn a sentence into one SQL statement.

Viva: this file does not run SQL. It only asks the model and reads the JSON reply.
routers/llm.py decides whether that SQL is a read or a change.
"""

from __future__ import annotations

import json
import re
from typing import Any

import google.generativeai as genai

from config import get_settings

SYSTEM_PROMPT = """\
You are an intelligent database assistant for a Student Management System. You help users manage their database tables and records using natural language.

CURRENT DATABASE SCHEMA:
{schema_context}

CAPABILITIES:
- Create new tables with specified columns and data types
- Modify table structure (add/remove/rename columns, change data types)
- Insert, update, and delete records
- Query and search for specific data
- Provide data analysis and summaries

RULES:
1. Always generate valid PostgreSQL SQL
2. For ANY data modification (INSERT, UPDATE, DELETE, ALTER, DROP), you MUST first show what will be affected
3. Use the format: First explain what you'll do, then show the SQL. The application asks the user to type their password before anything runs.
4. For UPDATE/DELETE: write a WHERE clause that identifies the exact row, such as a student number. The application loads the current row and shows it before the password prompt.
5. Be helpful and explain what each operation does
6. If the request is ambiguous, ask clarifying questions
7. Format your responses clearly with sections

RESPONSE FORMAT (JSON):
{
  "type": "info" | "sql_preview" | "confirm_action" | "error",
  "message": "Human readable explanation",
  "sql": "The SQL query (if applicable)",
  "preview_data": [],
  "action_id": "unique_id (for confirm_action type, leave empty otherwise)"
}

IMPORTANT:
- ALWAYS respond with valid JSON matching the format above. Do not include any text outside the JSON object.
- For SELECT queries that only read data, use type "info" and put query results in the message.
- For data-modifying queries (INSERT, UPDATE, DELETE, CREATE, ALTER, DROP), use type "confirm_action" so the user can confirm before execution.
- When showing preview data (e.g., rows that will be affected), include them in "preview_data".
- For errors or when something is unclear, use type "error" with an explanation.
"""


class LLMService:
    """Wraps Google Gemini generative AI for SQL generation and chat."""

    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite",
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                top_p=0.95,
                max_output_tokens=4096,
            ),
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def generate_response(
        self,
        user_message: str,
        schema_context: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict:
        """Send a user message together with schema context to Gemini.

        Returns the parsed JSON response dict or a fallback error dict.
        """
        system_prompt = SYSTEM_PROMPT.replace("{schema_context}", schema_context)

        # Build message parts
        contents: list[dict[str, Any]] = []

        # Add system context as first user turn
        contents.append({"role": "user", "parts": [system_prompt]})
        contents.append({
            "role": "model",
            "parts": [
                '{"type": "info", "message": "I understand. I am ready to help you manage your Student Management System database. What would you like to do?", "sql": "", "preview_data": [], "action_id": ""}'
            ],
        })

        # Append conversation history
        if conversation_history:
            for entry in conversation_history:
                role = "user" if entry.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [entry["content"]]})

        # Append current user message
        contents.append({"role": "user", "parts": [user_message]})

        try:
            response = self.model.generate_content(contents)
            raw_text = response.text.strip()
            return self._parse_response(raw_text)
        except Exception as exc:
            return {
                "type": "error",
                "message": f"Failed to generate response: {exc}",
                "sql": "",
                "preview_data": [],
                "action_id": "",
            }

    def generate_sql_from_natural_language(
        self, request: str, schema_context: str
    ) -> str:
        """Generate a single SQL statement from a natural-language request."""
        prompt = (
            f"Given this database schema:\n{schema_context}\n\n"
            f"Generate ONLY the PostgreSQL SQL query for: {request}\n"
            "Return ONLY the SQL, no explanation."
        )
        try:
            response = self.model.generate_content(prompt)
            sql = response.text.strip()
            # Strip markdown code fences if present
            sql = re.sub(r"^```(?:sql)?\s*", "", sql)
            sql = re.sub(r"\s*```$", "", sql)
            return sql.strip()
        except Exception as exc:
            return ""

    @staticmethod
    def format_schema_context(schema: dict) -> str:
        """Format a schema dictionary into a human-readable text block."""
        if not schema:
            return "No tables exist yet."

        lines: list[str] = []
        for table_name, info in schema.items():
            row_count = info.get("row_count", 0)
            lines.append(f"Table: {table_name} ({row_count} rows)")
            columns = info.get("columns", [])
            for col in columns:
                col_name = col.get("column_name", col.get("name", ""))
                data_type = col.get("data_type", col.get("type", ""))
                nullable = col.get("is_nullable", "YES")
                pk = col.get("is_primary_key", False)
                unique = col.get("is_unique", False)
                extras: list[str] = []
                if pk:
                    extras.append("PRIMARY KEY")
                if unique and not pk:
                    extras.append("UNIQUE")
                if nullable == "NO":
                    extras.append("NOT NULL")
                extra_str = f" ({', '.join(extras)})" if extras else ""
                lines.append(f"  - {col_name}: {data_type}{extra_str}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Try to extract a JSON object from the model's raw text."""
        # Strip markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Attempt to find a JSON object within the text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback – return the raw text as an "info" message
        return {
            "type": "info",
            "message": raw,
            "sql": "",
            "preview_data": [],
            "action_id": "",
        }


# Module-level singleton
llm_service = LLMService()
