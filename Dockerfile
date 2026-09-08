# Glama (https://glama.ai/mcp/servers) requires a Dockerfile that starts the
# server and responds to MCP introspection over stdio -- see the awesome-mcp-servers
# PR #12148 bot comment. This mirrors the same package/entrypoint already published
# to PyPI as macaroonnetwork-mcp (see pyproject.toml's [project.scripts]) and the
# uvx-based stdio invocation already registered at
# https://registry.modelcontextprotocol.io (com.macaroonnetwork/mcp-server).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY macaroonnetwork_mcp ./macaroonnetwork_mcp

RUN pip install --no-cache-dir .

# Talks MCP over stdio, same as every other client (Claude Desktop, uvx, etc.) --
# no network port, no server-held secrets, no required env vars to start.
ENTRYPOINT ["macaroonnetwork-mcp"]
