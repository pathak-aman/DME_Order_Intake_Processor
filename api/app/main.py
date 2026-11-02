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

try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")
except Exception as e:
    logger.warning("Could not auto-create database tables on startup: %s", e)

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

# ─── Global Exception Handlers ───────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(orders.router)

# ─── Health Checks & API root ─────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
@app.get("/api/health", tags=["System"], summary="Health check alias")
def health_check() -> dict:
    is_sqlite = settings.DATABASE_URL.strip().startswith("sqlite")
    return {
        "status": "ok",
        "service": "GenHealth DME Order Intake API",
        "database": "sqlite_local" if is_sqlite else "postgresql_connected",
    }


@app.get("/api", tags=["System"], summary="API root")
@app.get("/api/", tags=["System"], summary="API root slash")
def api_root() -> dict:
    return {
        "message": "GenHealth DME Order Intake API is running",
        "docs": "/docs",
        "health": "/health",
    }

# ─── Request Logging Middleware ───────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("← %s %s [%d]", request.method, request.url.path, response.status_code)
    return response
