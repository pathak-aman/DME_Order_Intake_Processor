"""Vercel FastAPI framework entrypoint.

With the FastAPI framework preset, Vercel forwards request paths directly to
this app rather than rewriting them to a file in /api.
"""
import os
import sys

api_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.main import app  # noqa: E402,F401