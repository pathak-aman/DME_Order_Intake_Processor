"""
Vercel serverless entry point.
Vercel expects a WSGI/ASGI app exported as `app` from api/index.py.
We import the FastAPI app from the backend package.
"""
import sys
import os

# Add backend directory to path so `app` package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app  # noqa: F401, E402

