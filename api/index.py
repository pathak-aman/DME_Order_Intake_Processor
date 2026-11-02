"""
Vercel serverless entry point.
Vercel expects a WSGI/ASGI app exported as `app` from api/index.py.
We import the FastAPI app from the backend package.
"""
import sys
import os

# Add root directory to sys.path so python can resolve 'backend' imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import app

