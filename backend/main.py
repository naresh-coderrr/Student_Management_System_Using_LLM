"""Start the API.

Viva: this file only starts the server and checks who is calling.
The real work is in routers/. Login and first-time password setup are public.
Every other /api route needs a token for one of the three emails in security.py.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import supabase_public
from routers import auth, tables, records, llm, audit
from security import is_allowed_email, normalize_email
from services.rag_service import rag_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # ── Startup ──────────────────────────────────────────────────────
    print("[Startup] Initializing RAG service …")
    try:
        rag_service.initialize()
        print("[Startup] RAG service initialized.")
    except Exception as exc:
        print(f"[Startup] RAG initialization warning: {exc}")
    yield
    # ── Shutdown ─────────────────────────────────────────────────────
    print("[Shutdown] Cleaning up …")


settings = get_settings()

app = FastAPI(
    title="Student Management System API",
    description="Backend API for managing students, tables, and records with LLM assistance.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────

origins = [
    settings.frontend_url,
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/activate"}


@app.middleware("http")
async def require_allowed_account(request: Request, call_next):
    """Every data route requires a session for one of the three approved emails."""
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path.rstrip("/") or "/"
    if not path.startswith("/api") or path in PUBLIC_PATHS:
        return await call_next(request)

    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else header
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Sign in required."})
    try:
        user = supabase_public.auth.get_user(token).user
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Session expired. Sign in again."})
    email = normalize_email(user.email or "")
    if not is_allowed_email(email):
        return JSONResponse(
            status_code=403,
            content={"detail": "This account is not allowed to use Student Management System."},
        )
    request.state.user_email = email
    return await call_next(request)

# ── Routers ───────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(tables.router)
app.include_router(records.router)
app.include_router(llm.router)
app.include_router(audit.router)


# ── Health check ──────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Student Management System API"}
