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

from app.main import app as base_app  # noqa: E402


class VercelPathNormalizerASGI:
    """
    Raw ASGI middleware that runs BEFORE FastAPI route matching.

    Vercel's @vercel/python builder rewrites scope['path'] to the destination
    file (e.g. '/api/index.py') instead of the original request path
    (e.g. '/auth/register'). The original path is preserved in Vercel's
    'x-forwarded-uri' header (raw bytes in the ASGI scope).

    By wrapping at the raw ASGI level here — before FastAPI ever sees the
    scope — we restore scope['path'] so FastAPI routes the request correctly.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))

            # Vercel sets the original request path in x-forwarded-uri
            forwarded_uri = headers.get(b"x-forwarded-uri", b"").decode("utf-8")
            forwarded_path = headers.get(b"x-forwarded-path", b"").decode("utf-8")
            matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")

            real_path = forwarded_uri or forwarded_path or matched_path

            current_path = scope.get("path", "")

            # Vercel has clobbered the path to the file destination — restore it
            if current_path in ("/api/index.py", "/api/index", "/api", "/", "") and real_path:
                real_path = real_path.split("?")[0]
                scope["path"] = real_path
                scope["raw_path"] = real_path.encode("utf-8")

            # Strip /api/index.py/ prefix if Vercel appended the path after it
            elif current_path.startswith("/api/index.py/"):
                cleaned = current_path[len("/api/index.py"):]
                scope["path"] = cleaned
                scope["raw_path"] = cleaned.encode("utf-8")

        await self.app(scope, receive, send)


# Vercel Python runtime looks for a variable named 'app' in this file
app = VercelPathNormalizerASGI(base_app)

