"""Turns an unhandled exception into a JSON 500 that still carries CORS headers.

Starlette's own handler for this sits outside CORSMiddleware, so a browser sees a crash as
a blocked request and the UI wrongly reports the API as unreachable.
"""
from __future__ import annotations

import logging

from fastapi.responses import JSONResponse

logger = logging.getLogger("app")


class CatchUnhandledErrors:
    """Plain ASGI middleware, so it never buffers the chat's event stream."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope["method"], scope["path"])
            if started:      # part of the response is already out, so all that's left is to drop the connection
                raise
            response = JSONResponse({"detail": "Something went wrong on the server. Please try again."}, status_code=500)
            await response(scope, receive, send)
