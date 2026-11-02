"""FastAPI application factory."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.routers import auth, orders

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Create Tables ────────────────────────────────────────────────────────────

# In production, prefer Alembic migrations. For the MVP we create tables on startup.
Base.metadata.create_all(bind=engine)

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
    license_info={"name": "Proprietary"},
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your Vercel domain in production
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
        content={"detail": "An internal server error occurred. Please try again."},
    )

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(orders.router)

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
def health_check() -> dict:
    return {"status": "ok", "service": "GenHealth DME Order Intake API"}

# ─── Request Logging Middleware ───────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("← %s %s [%d]", request.method, request.url.path, response.status_code)
    return response
