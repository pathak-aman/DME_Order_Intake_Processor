"""
Vercel catch-all serverless function entry point.

By naming this file [...path].py, Vercel natively passes the full original
request path (e.g. /auth/register) directly to the ASGI app scope without
any rewriting. No path-fix middleware is needed.
"""
import os
import sys

# Ensure both api/ and root directory are in sys.path
api_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(api_dir)

for p in (api_dir, root_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.main import app  # noqa: E402
