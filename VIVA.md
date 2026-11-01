# Viva walkthrough — Student Management System

Say this first, then open the file the examiner points at. The note at the top of that file matches this page.

## Files to open, in this order

Do not explain `frontend/src/components/ui`. Those files are only the buttons, cards, and dialogs.

1. `frontend/src/app/page.tsx` — sign-in screen
2. `frontend/src/lib/api.ts` — every button calls the Python API from here
3. `frontend/src/components/hover-chat.tsx` — the round chat button
4. `frontend/src/app/studio/page.tsx` — registry home
5. `frontend/src/app/studio/tables/page.tsx` — design a table
6. `frontend/src/app/studio/tables/[name]/page.tsx` — rows, edit, rename, export
7. `backend/main.py` — starts the API and checks the three emails
8. `backend/security.py` — the three allowed emails
9. `backend/routers/auth.py` — login
10. `backend/routers/tables.py` — create and rename tables
11. `backend/routers/records.py` — add, edit, delete rows
12. `backend/routers/llm.py` — chatbot: show the old row, then wait for the password
13. `backend/services/llm_service.py` — asks Gemini for the SQL
14. `backend/services/rag_service.py` — “How to use” answers from the guide
15. `backend/services/supabase_service.py` — sends the SQL to Supabase
16. `backend/setup.sql` — run once in Supabase so those SQL functions exist

## One-sentence answer

This is a student registry. The website is Next.js. The API is Python FastAPI. The data lives in Supabase. A Gemini chatbot can change the data only after it shows the current row and the user types their password.

## The two halves

1. **Website** — `frontend/`. The user signs in, designs tables, edits rows, and uses the round chat button.
2. **API** — `backend/`. `main.py` starts the server. Each folder under `routers/` is one job: login, tables, records, chatbot, activity log.

The website never talks to Supabase directly for table changes. It calls `http://localhost:8000`. The API then calls Supabase. That is in `frontend/src/lib/api.ts`.

## How one request travels

1. The page calls `api()` with the saved login token.
2. `main.py` checks the token. Only three emails are allowed. The list is in `backend/security.py`.
3. The matching router builds one SQL statement.
4. `services/supabase_service.py` runs that SQL by calling a function already created in Supabase (`exec_sql` or `exec_sql_query`).
5. Those functions were created once by running `backend/setup.sql` in the Supabase SQL Editor.

## What to say about each part

**Login.** `routers/auth.py`. First visit uses `/api/auth/activate` and stores the password in Supabase Auth. Later visits use `/api/auth/login`. Any other email is rejected before a password check.

**Tables.** `routers/tables.py`. The user chooses the table name, column names, data types, and which column is the primary key. The API builds `CREATE TABLE` or `ALTER TABLE`. It does not use a fixed student schema.

**Records.** `routers/records.py`. Insert, update, delete, search, and CSV export. An update reads the old row first, then writes the new values, then stores both in the activity log.

**Chatbot.** `routers/llm.py` and `services/llm_service.py`.
- A question that only reads data runs immediately.
- A change (insert, update, delete, create, alter, drop) is saved as a pending action and is not run yet.
- For an update or delete, the API first runs a `SELECT` so the user sees the old values.
- The user types their password. `confirm` checks that password, then runs the SQL.
- Say: “The model suggests the SQL. The program decides whether it is allowed to run.”

**Guide inside the chat (“How to use”).** `services/rag_service.py`. The help text in `backend/rag_docs/app_guide.md` is split into small pieces and stored in ChromaDB. A question searches those pieces, and Gemini answers from the pieces it found. That is RAG: retrieval, then generation. The model is not answering from memory of the whole guide.

**Activity.** `routers/audit.py`. Every create, edit, delete, and approved chatbot action is written to `audit_log`.

## Five questions they often ask

**Why FastAPI and Next.js?** Python is the backend I can explain line by line. Next.js with shadcn is only the screen. They meet at the API.

**Why not let Gemini run SQL itself?** The model can be wrong. The API keeps the SQL until the signed-in user confirms with a password.

**What is a primary key?** The column that identifies one row, for example a student number. The table designer sends `PRIMARY KEY` for the column the user ticks.

**What is Supabase here?** Hosted PostgreSQL plus login. The secret key is only on the API machine, in `backend/.env`. The browser never sees it.

**What does setup.sql do?** It creates `exec_sql`, `exec_sql_query`, the functions that list tables and columns, and the `audit_log` table. Without that file, the API has no way to run `CREATE TABLE`.
