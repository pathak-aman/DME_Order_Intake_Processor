"""
Vercel Serverless Function entry point.
Exports the ASGI handler for Vercel Python runtime.
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
from app.main import app  # noqa: E402


class VercelPathFixMiddleware:
    """
    ASGI middleware that runs at the lowest level (before FastAPI routing).

    Vercel's @vercel/python builder rewrites the ASGI scope['path'] to the
    destination file path (e.g. '/api/index.py') instead of the original
    requested path (e.g. '/auth/register'). The original path is preserved
    in the 'x-forwarded-uri' request header as raw bytes in the ASGI scope.

    This middleware restores scope['path'] to the original path so FastAPI
    can route the request correctly.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))

            # x-forwarded-uri holds the original request path (e.g. /auth/register)
            forwarded_uri = headers.get(b"x-forwarded-uri", b"").decode("utf-8")
            # x-matched-path is a secondary fallback
            matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")

            real_path = forwarded_uri or matched_path

            if real_path:
                # Strip query string if present
                real_path = real_path.split("?")[0]
                # Only override if Vercel has clobbered the path to the file path
                if scope.get("path", "").rstrip("/") in (
                    "/api/index.py",
                    "/api/index",
                    "/api",
                    "",
                    "/",
                ):
                    scope["path"] = real_path
                    # Keep raw_path in sync
                    scope["raw_path"] = real_path.encode("utf-8")

        await self.app(scope, receive, send)


# Wrap the FastAPI app — Vercel will call this as the ASGI handler
handler = VercelPathFixMiddleware(app)

