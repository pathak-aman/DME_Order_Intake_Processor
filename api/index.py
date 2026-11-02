"""
Vercel Serverless Function entry point.
Exports FastAPI `app` for Vercel Python runtime.
"""
import os
import sys

# Ensure both api/ and root directory are in sys.path
api_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(api_dir)

for path in (api_dir, root_dir):
    if path not in sys.path:
        sys.path.insert(0, path)

# Import the FastAPI app instance from api/app/main.py
from app.main import app  # noqa: E402, F401
