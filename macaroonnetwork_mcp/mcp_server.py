"""macaroonnetwork-mcp — MCP server for Macaroon Network.

Four tools:

- macaroons_search / macaroons_metadata: free, no payment, no wallet
  needed.
- macaroons_purchase / macaroons_execute: pay via Lightning L402. By
  default (MACAROONS_BUYER_LND_MODE unset or "none") this package holds no
  wallet and attempts no payment -- a 402 comes back as a payment_required
  tool result carrying the real hold invoice and macaroon, for YOU to pay
  with whatever Lightning wallet you actually have, then retry the same
  tool call with resume_macaroon set to that macaroon. A plain retry
  without resume_macaroon mints a brand-new hold instead of resuming the
  one you just paid -- see PaymentRequired's docstring in exceptions.py.

Set MACAROONS_BUYER_LND_MODE=external plus LND_BUYER_HOST/LND_BUYER_TLS/
LND_BUYER_MACAROON if you have your own real LND node and want this
package to auto-pay from it instead.

Talks to https://api.macaroonnetwork.com by default -- override with
MACAROONS_REGISTRY_URL / MACAROONS_FEED_URL for local development.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .client import MacaroonClient
from .exceptions import (
    PaymentRequired,
    PayloadTampered,
    PredicateNotSatisfied,
    ReceiptMismatch,
    SpendCapExceeded,
)

_REGISTRY_URL = os.environ.get("MACAROONS_REGISTRY_URL", "https://api.macaroonnetwork.com")
_FEED_URL = os.environ.get("MACAROONS_FEED_URL", "https://api.macaroonnetwork.com")
_DEFAULT_PER_CALL_CAP_SATS = 100

_client = MacaroonClient(
    registry_url=_REGISTRY_URL,
    feed_url=_FEED_URL,
    max_spend_msat=int(os.environ.get("MACAROONS_SESSION_BUDGET_SATS", "1000")) * 1000,
    price_msat=int(os.environ.get("MACAROONS_PRICE_MSAT", "1000")),
)


def get_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "macaroons_search",
            "description": (
                "Search Macaroon Network for capabilities matching an intent. "
                "Returns ranked listings with price, predicate hash, and freshness. "
                "Free, no payment required."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": (
                            "Natural language description of what the agent needs. "
                            "E.g. 'GPU pricing data updated in the last 24 hours'"
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "maximum": 20,
                        "description": "Maximum number of results to return",
                    },
                },
                "required": ["intent"],
            },
        },
        {
            "name": "macaroons_metadata",
            "description": (
                "Get free metadata for a feed target before purchasing. Returns "
                "freshness and content_hash. No payment required."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target_id": {
                        "type": "string",
                        "description": "The feed target id (e.g. 'runpod').",
                    },
                },
                "required": ["target_id"],
            },
        },
        {
            "name": "macaroons_purchase",
            "description": (
                "Purchase change-events for a feed target. Pays via Lightning L402 "
                "against a hold invoice — payment only settles if the acceptance "
                "predicate passes against the delivered payload; otherwise it is "
                "fully refunded. If no wallet is configured (the default), returns "
                "payment_required with a real invoice for you to pay yourself."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target_id": {
                        "type": "string",
                        "description": "The feed target id from macaroons_metadata",
                    },
                    "predicate": {
                        "type": "object",
                        "description": (
                            "Acceptance predicate. Payment only settles if this passes "
                            "against the real delivered payload."
                        ),
                    },
                    "max_spend_sats": {
                        "type": "integer",
                        "default": _DEFAULT_PER_CALL_CAP_SATS,
                        "description": "Hard per-call spend cap in satoshis.",
                    },
                    "since": {
                        "type": "string",
                        "description": (
                            "ISO-8601 timestamp — only change-events after this are "
                            "considered. Defaults to 30 days ago."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "Maximum number of change-events to return",
                    },
                    "resume_macaroon": {
                        "type": "string",
                        "description": (
                            "Only set this after a prior call returned "
                            "payment_required and you've since paid that invoice "
                            "with your own wallet — set it to the macaroon that "
                            "call returned. Omit on a first attempt."
                        ),
                    },
                },
                "required": ["target_id", "predicate"],
            },
        },
        {
            "name": "macaroons_execute",
            "description": (
                "Execute a paid marketplace capability by capability_id. Pays via "
                "Lightning L402 against a hold invoice — payment only settles if "
                "the acceptance predicate passes against the bridge response; bridge "
                "errors and predicate failures refund. If no wallet is configured "
                "(the default), returns payment_required with a real invoice for "
                "you to pay yourself."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "capability_id": {
                        "type": "string",
                        "description": (
                            "Registry capability_id, e.g. "
                            "'polymathica-heated-channel-v1'."
                        ),
                    },
                    "input": {
                        "type": "object",
                        "description": "Capability input payload matching the listing input_schema.",
                    },
                    "predicate": {
                        "type": "object",
                        "description": (
                            "Optional acceptance predicate. Defaults to the listing's "
                            "sample_predicate when omitted."
                        ),
                    },
                    "max_spend_sats": {
                        "type": "integer",
                        "default": _DEFAULT_PER_CALL_CAP_SATS,
                        "description": "Hard per-call spend cap in satoshis.",
                    },
                    "resume_macaroon": {
                        "type": "string",
                        "description": (
                            "Only set this after a prior call returned "
                            "payment_required and you've since paid that invoice "
                            "with your own wallet — set it to the macaroon that "
                            "call returned. Omit on a first attempt."
                        ),
                    },
                },
                "required": ["capability_id", "input"],
            },
        },
    ]


def _ok(data: Any) -> dict[str, Any]:
    return {"isError": False, "content": [{"type": "text", "text": json.dumps(data)}]}


def _error(message: str) -> dict[str, Any]:
    return {"isError": True, "content": [{"type": "text", "text": message}]}


def _payment_required(exc: PaymentRequired) -> dict[str, Any]:
    """Not a failure -- see this module's own docstring. A PLAIN retry
    (identical arguments, no resume_macaroon) would mint a BRAND NEW hold
    rather than resuming this one, orphaning whatever you just paid."""
    return _ok({
        "payment_required": True,
        "invoice": exc.bolt11,
        "macaroon": exc.macaroon,
        "amount_msat": exc.amount_msat,
        "instructions": (
            "Pay this BOLT11 invoice with your own Lightning wallet, then call "
            "this same tool again with identical arguments PLUS "
            "resume_macaroon set to the macaroon above. A retry without "
            "resume_macaroon mints a new invoice instead of using this one."
        ),
    })


def _default_since() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _search(args: dict[str, Any]) -> dict[str, Any]:
    def _do() -> list[dict[str, Any]]:
        resp = requests.get(
            f"{_REGISTRY_URL}/listings/search",
            params={"intent": args["intent"], "limit": args.get("limit", 5)},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("listings", [])

    return _ok(await asyncio.to_thread(_do))


async def _metadata(args: dict[str, Any]) -> dict[str, Any]:
    meta = await asyncio.to_thread(_client.metadata, args["target_id"])
    return _ok(meta)


async def _purchase(args: dict[str, Any]) -> dict[str, Any]:
    target_id = args["target_id"]
    predicate = args["predicate"]
    max_spend_sats = args.get("max_spend_sats", _DEFAULT_PER_CALL_CAP_SATS)
    since = args.get("since") or _default_since()
    limit = args.get("limit", 100)
    resume_macaroon = args.get("resume_macaroon")

    if _client.price_msat > max_spend_sats * 1000:
        return _error(
            f"SpendCapExceeded: listing price {_client.price_msat}msat exceeds "
            f"per-call cap {max_spend_sats * 1000}msat"
        )

    def _do() -> dict[str, Any]:
        meta = _client.metadata(target_id)
        commitment = _client.commit(meta, predicate)
        return _client.purchase(
            commitment, since=since, limit=limit, resume_macaroon=resume_macaroon
        )

    try:
        result = await asyncio.to_thread(_do)
    except PaymentRequired as exc:
        return _payment_required(exc)
    except SpendCapExceeded as exc:
        return _error(f"SpendCapExceeded: {exc}")
    except PredicateNotSatisfied as exc:
        return _error(f"PredicateNotSatisfied: {exc}")
    except PayloadTampered as exc:
        return _error(f"PayloadTampered: {exc}")

    return _ok({
        "payload": result["payload"],
        "receipt": result["receipt"],
        "tamper_check": "passed",
        "spent_sats": _client.spent_msat / 1000,
    })


async def _execute(args: dict[str, Any]) -> dict[str, Any]:
    capability_id = args["capability_id"]
    input_payload = args["input"]
    predicate = args.get("predicate")
    max_spend_sats = args.get("max_spend_sats", _DEFAULT_PER_CALL_CAP_SATS)
    resume_macaroon = args.get("resume_macaroon")

    def _do() -> dict[str, Any]:
        return _client.execute_capability(
            capability_id,
            input_payload,
            predicate,
            max_spend_sats=max_spend_sats,
            resume_macaroon=resume_macaroon,
        )

    try:
        result = await asyncio.to_thread(_do)
    except PaymentRequired as exc:
        return _payment_required(exc)
    except SpendCapExceeded as exc:
        return _error(f"SpendCapExceeded: {exc}")
    except PredicateNotSatisfied as exc:
        return _error(f"PredicateNotSatisfied: {exc}")
    except PayloadTampered as exc:
        return _error(f"PayloadTampered: {exc}")
    except ReceiptMismatch as exc:
        return _error(f"ReceiptMismatch: {exc}")

    return _ok({
        "payload": result["payload"],
        "receipt": result["receipt"],
        "tamper_check": "passed",
        "spent_sats": _client.spent_msat / 1000,
    })


async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "macaroons_search":
        return await _search(arguments)
    if name == "macaroons_metadata":
        return await _metadata(arguments)
    if name == "macaroons_purchase":
        return await _purchase(arguments)
    if name == "macaroons_execute":
        return await _execute(arguments)
    return _error(f"unknown tool: {name}")


def _build_mcp_server():
    """Wires get_tool_definitions()/call_tool() into a real mcp.server.Server
    for stdio use. Imported lazily so offline unit tests (which only need
    get_tool_definitions()/call_tool()) never require the mcp package."""
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    async def on_list_tools(ctx, params):
        tools = [
            types.Tool(
                name=t["name"], description=t["description"], input_schema=t["inputSchema"]
            )
            for t in get_tool_definitions()
        ]
        return types.ListToolsResult(tools=tools)

    async def on_call_tool(ctx, params):
        result = await call_tool(params.name, params.arguments or {})
        content = [types.TextContent(type="text", text=item["text"]) for item in result["content"]]
        return types.CallToolResult(content=content, is_error=result["isError"])

    server = Server(
        "macaroon-network",
        version="0.2.0",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )
    return server, stdio_server


async def _main() -> None:
    server, stdio_server = _build_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Console-script entry point (see pyproject.toml [project.scripts])."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
