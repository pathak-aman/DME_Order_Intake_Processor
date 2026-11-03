"""FastAPI application factory."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.routers import auth, orders

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Create Tables ────────────────────────────────────────────────────────────

def init_tables():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.warning("Could not auto-create database tables on startup: %s", e)

init_tables()

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GenHealth DME Order Intake API",
    description=(
        "AI-native REST API for processing durable medical equipment (DME) orders. "
        "Accepts faxed PDF orders, extracts clinical fields with strict validation, "
        "and manages orders with per-user isolation."
    ),
    version="1.0.0",
    contact={"name": "GenHealth Engineering", "email": "engineering@genhealth.ai"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Vercel Path Normalization Middleware ─────────────────────────────────────

@app.middleware("http")
async def vercel_path_normalizer(request: Request, call_next):
    """
    Normalizes request paths when running inside Vercel serverless environment.
    If Vercel rewrites a request to /api/index.py, the original path is preserved
    in x-matched-path header.
    """
    original_path = request.scope.get("path", "")
    matched_path = request.headers.get("x-matched-path")

    # If Vercel rewrote internal path to entrypoint, restore the matched path
    if matched_path and original_path in ("/api/index.py", "/api/index", "/api", "/"):
        logger.info(f"Vercel rewrite detected: mapping {original_path} -> {matched_path}")
        request.scope["path"] = matched_path

    logger.info(f"→ {request.method} {request.scope.get('path')} (incoming: {original_path})")
    response = await call_next(request)
    logger.info(f"← {request.method} {request.scope.get('path')} [{response.status_code}]")
    return response

# ─── Startup Event ────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_tables()

# ─── Global Exception Handlers ───────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )

# ─── Routers (Mounted both at root and /api for seamless proxying) ─────────────

# Standard routes: /auth/register, /auth/token, /orders/, etc.
app.include_router(auth.router)
app.include_router(orders.router)

# Prefix routes: /api/auth/register, /api/auth/token, /api/orders/, etc.
app.include_router(auth.router, prefix="/api")
app.include_router(orders.router, prefix="/api")

# ─── Health Checks & API root ─────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
@app.get("/api/health", tags=["System"], summary="Health check alias")
def health_check() -> dict:
    is_sqlite = settings.DATABASE_URL.strip().startswith("sqlite")
    return {
        "status": "ok",
        "service": "GenHealth DME Order Intake API",
        "database": "sqlite_local" if is_sqlite else "postgresql_neon",
    }


@app.get("/api", tags=["System"], summary="API root")
@app.get("/api/", tags=["System"], summary="API root slash")
def api_root() -> dict:
    return {
        "message": "GenHealth DME Order Intake API is running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "register": "POST /auth/register",
            "token": "POST /auth/token",
            "orders": "GET /orders/",
            "upload": "POST /orders/upload",
        },
    }
