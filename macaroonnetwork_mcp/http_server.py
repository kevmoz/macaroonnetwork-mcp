"""Streamable-HTTP transport for macaroonnetwork-mcp.

The existing package (mcp_server.py) only ships a stdio transport, which
covers Claude Desktop-style local clients but not platforms that need to
plug in a hosted MCP server by URL (e.g. Coze's "paste the MCP tool's
URL" plugin flow, which requires an HTTPS endpoint, not a locally-run
stdio process).

This module wraps the *same* tool definitions and call_tool() logic from
mcp_server.py -- no duplicated tool implementations -- behind a real
mcp.server.streamable_http_manager.StreamableHTTPSessionManager, served
over ASGI/uvicorn. Run directly for local testing:

    uvicorn macaroonnetwork_mcp.http_server:app --port 8765

Not yet deployed anywhere. Built and tested locally only.
"""
from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .mcp_server import _build_mcp_server


def _build_app() -> Starlette:
    from mcp.server.streamable_http_manager import (
        StreamableHTTPASGIApp,
        StreamableHTTPSessionManager,
    )

    server, _stdio_server = _build_mcp_server()
    session_manager = StreamableHTTPSessionManager(app=server, json_response=True)
    http_app = StreamableHTTPASGIApp(session_manager)

    async def health(_request):
        return JSONResponse({"status": "ok", "server": "macaroonnetwork-mcp"})

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/health", health),
            Mount("/mcp", app=http_app),
        ],
        lifespan=lifespan,
    )


app = _build_app()
