# Student Management System – User Guide

Welcome to the **Student Management System (SMS)**! This comprehensive guide will walk
you through every feature of the application so you can manage your academic data with
confidence.

---

## 1. What Is the Student Management System?

The Student Management System is a web-based application that lets administrators,
faculty, and staff manage student-related data through an intuitive interface backed
by a powerful relational database (PostgreSQL via Supabase). Key capabilities include:

- **Dynamic table creation** – design your own tables without writing SQL.
- **Full CRUD operations** – create, read, update, and delete records from any table.
- **Natural-language assistant** – use the built-in LLM chatbot to perform database
  operations using plain English.
- **Audit logging** – every change is recorded for accountability.
- **Data export** – download any table's data as a CSV file.
- **Search & filter** – find exactly the records you need.

---

## 2. Getting Started

### 2.1 Who can sign in

Only these three accounts can use Student Management System:

- nareshramrajasimhan18@gmail.com
- nareshram4804@gmail.com
- nareshramstudies@gmail.com

Any other email is refused. The first time an approved email is used, choose **Set a password**. After that, use **Sign in**.

### 2.2 Logging In

1. Open the sign-in page.
2. Enter one of the three approved emails and its password.
3. Click **Sign in**.
4. You will land on the registry dashboard.

### 2.3 Logging Out

Click the **Logout** button in the top-right corner of any page.

---

## 3. Managing Tables

### 3.1 Viewing Existing Tables

From the dashboard, click **Tables** in the sidebar. You will see a list of all tables
along with their row counts and column summaries.

### 3.2 Creating a New Table

1. Click **Create Table**.
2. Enter a **table name** (letters, digits, and underscores only; must start with a
   letter or underscore).
3. Add one or more columns:
   - **Column name** – unique name within the table.
   - **Data type** – choose from TEXT, INTEGER, BIGINT, SERIAL, BIGSERIAL,
     VARCHAR(n), BOOLEAN, DATE, TIMESTAMP, TIMESTAMPTZ, NUMERIC, REAL,
     DOUBLE PRECISION, JSON, JSONB, or UUID.
   - **Primary key** – check this for the column that uniquely identifies each row
     (typically an auto-incrementing SERIAL or BIGSERIAL).
   - **Nullable** – uncheck to make the column required.
   - **Unique** – check to prevent duplicate values.
   - **Default value** – optional SQL expression used when no value is provided.
4. Click **Create** to build the table.

#### Example

| Column       | Type       | PK  | Nullable | Unique |
|-------------|-----------|-----|----------|--------|
| id          | SERIAL    | ✓   | ✗        | ✗      |
| first_name  | TEXT      | ✗   | ✗        | ✗      |
| last_name   | TEXT      | ✗   | ✗        | ✗      |
| email       | TEXT      | ✗   | ✗        | ✓      |
| enrolled_on | DATE      | ✗   | ✓        | ✗      |

### 3.3 Modifying a Table

Select a table and click **Edit Structure**. You can perform the following operations:

- **Rename table** – change the table's name.
- **Add column** – append a new column with a specified data type.
- **Drop column** – remove a column (data in that column will be lost).
- **Rename column** – change a column's name without losing data.
- **Change column type** – alter the data type of an existing column (may fail if
  existing data is incompatible with the new type).

### 3.4 Deleting a Table

1. Select the table you want to remove.
2. Click **Delete Table**.
3. Confirm the action in the dialog.

> **Warning:** Deleting a table is irreversible. All data within the table will be
> permanently lost.

---

## 4. Managing Records

### 4.1 Viewing Records

1. Select a table from the sidebar.
2. Records are displayed in a paginated table view.
3. Use the page controls at the bottom to navigate between pages.
4. Choose the number of records per page (10, 25, 50, or 100).

### 4.2 Inserting a New Record

1. Click **Add Record**.
2. Fill in the values for each column in the form. Fields with defaults can be left
   blank.
3. Click **Save**.

### 4.3 Updating a Record

1. Find the record you want to edit.
2. Click the **Edit** (pencil) icon on that row.
3. Modify the values you need to change.
4. Click **Save**.

The system will capture both the old and new data for the audit log.

### 4.4 Deleting a Record

1. Click the **Delete** (trash) icon on the row you want to remove.
2. Confirm the deletion.

The deleted record's data is preserved in the audit log.

### 4.5 Bulk Insert

1. Click **Bulk Insert**.
2. Prepare your data as a list of JSON objects (one per record).
3. Paste the JSON into the input area.
4. Click **Insert All**.

#### Example JSON for Bulk Insert

```json
[
  {"first_name": "Alice", "last_name": "Smith", "email": "alice@example.com"},
  {"first_name": "Bob", "last_name": "Jones", "email": "bob@example.com"},
  {"first_name": "Carol", "last_name": "Lee", "email": "carol@example.com"}
]
```

---

## 5. Searching and Filtering

### 5.1 Free-Text Search

Type a keyword in the **Search** box above the records table. The system searches
across all text-type columns and returns matching rows.

### 5.2 Column Filters

Click the **Filter** button to open the filter panel. You can add one or more
column-specific filters:

- Select a **column name**.
- Enter the **value** to match.
- Multiple filters are combined with AND logic.

### 5.3 Sorting

Click any **column header** to sort by that column. Click again to toggle between
ascending and descending order. An arrow indicator shows the active sort direction.

---

## 6. Exporting Data

1. Navigate to the table you want to export.
2. Click **Export CSV**.
3. A CSV file containing all records will be downloaded to your computer.

You can open the CSV in Excel, Google Sheets, or any spreadsheet application.

---

## 7. Using the LLM Assistant

The built-in AI assistant lets you interact with your database using natural language.

### 7.1 Opening the Chat

Click the **AI Assistant** button (or the chat icon) to open the chat panel.

### 7.2 Example Commands

| What you type                                   | What happens                                          |
|------------------------------------------------|------------------------------------------------------|
| "Show me all students"                          | Runs a SELECT query and displays the results.         |
| "Add a new student named John Doe"              | Generates an INSERT statement and asks for confirm.   |
| "Create a grades table with student_id and gpa" | Generates CREATE TABLE SQL and asks for confirm.      |
| "Delete the student with id 42"                 | Shows the affected record and asks for confirmation.  |
| "How many students enrolled after 2023?"        | Runs a COUNT query and shows the result.              |
| "Rename the email column to contact_email"      | Generates ALTER TABLE SQL and asks for confirm.       |
| "What tables exist?"                            | Lists all current tables and their columns.           |

### 7.3 Confirmation Flow

The assistant may prepare any data or table command (insert, update, delete, create, alter, drop). Nothing runs until you approve it.

1. **Explain** what the operation will do.
2. **Show the SQL** that will be sent to Supabase.
3. **Load the current rows** when a record would change, including the previous name and the rest of that row.
4. **Ask for your password.** The change runs only after the password matches the account you are signed in with.

Click **Approve change** after the password is accepted, or **Cancel** to leave the data as it is. There is no starter table. Design the first table with the columns you need, including a primary key and a data type for each column. More tables can be added later from **Tables** or by asking the assistant.

### 7.4 Tips for Effective Prompts

- Be specific: "Add a boolean column called is_active to the students table" is
  better than "add a column".
- Reference table and column names directly when you know them.
- Ask follow-up questions — the assistant maintains conversation context.
- If the assistant's SQL looks wrong, tell it what to fix and it will regenerate.

---

## 8. Audit Log

Every database operation is recorded in the audit log.

### 8.1 What Is Logged

| Field        | Description                                        |
|-------------|---------------------------------------------------|
| Timestamp   | When the action occurred.                          |
| Table       | Which table was affected.                          |
| Action      | The type of action (INSERT, UPDATE, DELETE, etc.). |
| Old Data    | The data before the change (for UPDATE/DELETE).    |
| New Data    | The data after the change (for INSERT/UPDATE).     |
| Executed By | Who performed the action.                          |
| SQL Query   | The exact SQL that was run.                        |
| Description | A human-readable summary.                          |

### 8.2 Viewing the Audit Log

1. Navigate to **Audit Log** in the sidebar.
2. Use the filters to narrow by table name or action type.
3. Entries are shown in reverse-chronological order.

---

## 9. Data Types Reference

| Data Type          | Description                                    | Example Value             |
|-------------------|-----------------------------------------------|--------------------------|
| TEXT              | Variable-length string, no size limit.         | 'Hello World'            |
| INTEGER           | 32-bit signed integer.                        | 42                       |
| BIGINT            | 64-bit signed integer.                        | 9223372036854775807      |
| SERIAL            | Auto-incrementing 32-bit integer.             | (auto)                   |
| BIGSERIAL         | Auto-incrementing 64-bit integer.             | (auto)                   |
| VARCHAR(n)        | Variable-length string with max length n.      | 'Hello' (max n chars)    |
| BOOLEAN           | True or false.                                | true / false             |
| DATE              | Calendar date (no time).                       | '2024-01-15'             |
| TIMESTAMP         | Date and time (no timezone).                  | '2024-01-15 10:30:00'    |
| TIMESTAMPTZ       | Date and time with timezone.                  | '2024-01-15T10:30:00Z'   |
| NUMERIC           | Exact decimal number.                         | 3.14159                  |
| REAL              | 32-bit floating point.                        | 3.14                     |
| DOUBLE PRECISION  | 64-bit floating point.                        | 3.141592653589793        |
| JSON              | JSON data (text storage).                     | '{"key": "value"}'       |
| JSONB             | JSON data (binary storage, indexable).        | '{"key": "value"}'       |
| UUID              | Universally unique identifier.                | 'a0eebc99-9c0b-4ef8…'   |

---

## 10. Frequently Asked Questions

### Q: Can I undo a deletion?
**A:** Deleted records are removed from the database permanently. However, the audit
log retains the old data for reference. You can use the audit log to see what was
deleted and manually re-insert the data if needed.

### Q: Why is my table not showing up?
**A:** Make sure the table was created in the `public` schema. System tables and tables
in other schemas are not listed.

### Q: Can I import data from a CSV?
**A:** Yes! Use the **Bulk Insert** feature. Convert your CSV rows into JSON objects
and paste them into the bulk insert form.

### Q: What happens if I change a column's data type?
**A:** PostgreSQL will attempt to cast existing values to the new type. If any value
cannot be converted, the operation will fail with an error and no changes will be made.

### Q: Is there a limit to the number of records?
**A:** The system supports millions of records per table. Performance may vary based on
your Supabase plan and query complexity.

### Q: Can I use the AI assistant to create reports?
**A:** Yes! Ask the assistant questions like "Show me a summary of students by
enrollment year" or "What is the average GPA across all students?" and it will generate
the appropriate SQL.

### Q: How do I connect directly to the database?
**A:** You can use any PostgreSQL client (pgAdmin, DBeaver, psql) with the connection
details provided in your Supabase project dashboard.

### Q: Are my changes saved automatically?
**A:** Yes. Every operation (insert, update, delete) is executed immediately against
the database and logged in the audit trail.

---

## 11. Tips and Best Practices

1. **Always use a primary key.** Every table should have a unique identifier column
   (SERIAL or BIGSERIAL is recommended).

2. **Name things clearly.** Use descriptive table and column names:
   `student_enrollments` is better than `se`.

3. **Use appropriate data types.** Don't store numbers as TEXT — use INTEGER or NUMERIC
   for efficient queries and accurate sorting.

4. **Leverage the AI assistant.** For complex queries or unfamiliar SQL, let the
   assistant generate the query for you.

5. **Check the audit log regularly.** Stay informed about what changes have been made
   and by whom.

6. **Export backups.** Periodically export important tables as CSV files for off-site
   backup.

7. **Use NOT NULL constraints** for required fields to prevent incomplete data.

8. **Use UNIQUE constraints** for fields that should never have duplicate values
   (e.g., email addresses, student IDs).

9. **Keep tables normalized.** Avoid duplicating data across tables. Use foreign key
   relationships instead.

10. **Test with small data first.** Before performing bulk operations, try inserting
    a single record to verify column types and constraints.

---

## 12. Keyboard Shortcuts

| Shortcut           | Action                     |
|--------------------|-----------------------------|
| Ctrl + N           | Create new record           |
| Ctrl + S           | Save current changes        |
| Ctrl + F           | Open search bar             |
| Escape             | Close modal or cancel edit  |

---

## 13. Troubleshooting

### Problem: "Invalid table name" error
**Solution:** Table names must start with a letter or underscore and contain only
letters, digits, and underscores. Avoid spaces and special characters.

### Problem: "Column type mismatch" on insert
**Solution:** Make sure the value you're providing matches the column's data type. For
example, don't put text in an INTEGER column.

### Problem: "Permission denied" errors
**Solution:** Contact your administrator to ensure your account has the required
database permissions.

### Problem: The AI assistant gives incorrect SQL
**Solution:** Provide more context in your request. Specify table names and column
names explicitly. You can also correct the assistant and it will adjust.

### Problem: CSV export is empty
**Solution:** The table might have zero records. Check the row count on the tables
page before exporting.

---

## 14. Architecture Overview

The Student Management System consists of:

- **Frontend** – A React/Next.js application providing the user interface.
- **Backend** – A Python FastAPI server handling API requests, authentication, and
  database operations.
- **Database** – PostgreSQL hosted on Supabase with Row Level Security.
- **LLM Integration** – Google Gemini for natural-language database interaction.
- **RAG System** – ChromaDB-backed retrieval for contextual help answers.

All API endpoints are prefixed with `/api/` and follow RESTful conventions.

---

## 15. API Endpoint Summary

| Method | Endpoint                          | Description                        |
|--------|-----------------------------------|------------------------------------|
| POST   | /api/auth/login                   | Sign in                           |
| POST   | /api/auth/signup                  | Create account                    |
| POST   | /api/auth/logout                  | Sign out                          |
| GET    | /api/auth/me                      | Get current user                  |
| GET    | /api/tables/                      | List all tables                   |
| POST   | /api/tables/                      | Create a table                    |
| GET    | /api/tables/{name}                | Get table schema                  |
| PUT    | /api/tables/{name}                | Alter a table                     |
| DELETE | /api/tables/{name}                | Drop a table                      |
| GET    | /api/tables/{name}/stats          | Get table statistics              |
| GET    | /api/records/{table_name}         | Get records (paginated)           |
| POST   | /api/records/{table_name}         | Insert a record                   |
| PUT    | /api/records/{table_name}         | Update a record                   |
| DELETE | /api/records/{table_name}         | Delete a record                   |
| POST   | /api/records/{table_name}/bulk    | Bulk insert records               |
| POST   | /api/records/{table_name}/export  | Export records as CSV             |
| POST   | /api/llm/chat                     | Chat with AI assistant            |
| POST   | /api/llm/confirm                  | Confirm/cancel pending action     |
| POST   | /api/llm/help                     | Get help via RAG                  |
| GET    | /api/health                       | Health check                      |

---

*This guide is maintained as part of the Student Management System project.
Last updated: 2024.*
