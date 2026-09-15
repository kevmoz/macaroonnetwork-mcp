"""macaroonnetwork-mcp — MCP discovery server for Macaroon Network.

Search exposes the x402 marketplace, canonical categories, governed sources,
and specialised MCP servers, including source-labelled Christian evidence.

Six public tools:

- macaroons_search / macaroons_metadata: free, no payment, no wallet
  needed.
- macaroons_categories / macaroons_discover_mcp / macaroons_sources: free
  canonical network topology and reviewed source discovery.
- macaroons_execute: executes x402 products using USDC on Base. By default
  this package holds no wallet and attempts no payment; a 402 comes back as
  x402_payment_required with the exact terms for the caller to sign.

Legacy L402 implementation remains private for backward code compatibility,
but it is not advertised as a public MCP tool or payment option.

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
    X402PaymentRequired,
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
                            "E.g. 'source-labelled Christian scripture evidence'"
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "maximum": 20,
                        "description": "Maximum number of results to return",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Optional canonical category id from macaroons_categories."
                        ),
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
            "name": "macaroons_categories",
            "description": (
                "List Macaroon's canonical intelligence categories and exact mapped "
                "product counts. Free, no payment required."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "macaroons_discover_mcp",
            "description": "List evidenced live Macaroon MCP servers and transports. Free.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "macaroons_sources",
            "description": (
                "List reviewed source records, rights states, provenance requirements, "
                "and honest mapping coverage. Free."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "macaroons_execute",
            "description": (
                "Execute a paid marketplace capability by capability_id using x402 "
                "USDC on Base. Payment only "
                "settles if the acceptance predicate passes against the bridge "
                "response; bridge errors and predicate failures refund. If no "
                "wallet is configured (the default), returns "
                "x402_payment_required with the real payment "
                "terms for you to pay/sign yourself."
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
                    "payment_signature": {
                        "type": "string",
                        "description": (
                            "Only set this after a prior call returned "
                            "x402_payment_required and you've since signed the "
                            "exact-scheme USDC payment it described with your "
                            "own wallet — set it to the resulting signed proof. "
                            "Omit on a first attempt."
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


def _x402_payment_required(exc: X402PaymentRequired) -> dict[str, Any]:
    """Not a failure -- mirrors _payment_required()'s contract exactly, for
    the x402 rail instead of L402. This client never signs the payment
    itself; it hands back the real accepts[0] terms for YOU to sign with
    your own wallet/CDP infra, then retry the same tool call with
    payment_signature set to the resulting proof."""
    return _ok({
        "x402_payment_required": True,
        "resource_url": exc.resource_url,
        "amount_atomic": exc.amount_atomic,
        "asset": exc.asset,
        "network": exc.network,
        "pay_to": exc.pay_to,
        "extra_name": exc.extra_name,
        "extra_version": exc.extra_version,
        "max_timeout_seconds": exc.max_timeout_seconds,
        "x402_version": exc.x402_version,
        "instructions": (
            "Sign an exact x402 payment of amount_atomic atomic units of "
            "asset on network to pay_to with your own wallet/CDP infra, "
            "then call this same tool again with identical arguments PLUS "
            "payment_signature set to the resulting signed proof."
        ),
    })


def _default_since() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _search(args: dict[str, Any]) -> dict[str, Any]:
    def _do() -> list[dict[str, Any]]:
        params = {"query": args["intent"], "limit": args.get("limit", 5)}
        if args.get("category"):
            params["category"] = args["category"]
        resp = requests.get(
            f"{_REGISTRY_URL}/api/public/services/search",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("services", [])

    return _ok(await asyncio.to_thread(_do))


async def _public_registry_document(path: str) -> dict[str, Any]:
    def _do() -> dict[str, Any]:
        resp = requests.get(f"{_REGISTRY_URL}{path}", timeout=15)
        resp.raise_for_status()
        return resp.json()

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
    payment_signature = args.get("payment_signature")

    def _do() -> dict[str, Any]:
        return _client.execute_capability(
            capability_id,
            input_payload,
            predicate,
            max_spend_sats=max_spend_sats,
            resume_macaroon=resume_macaroon,
            payment_signature=payment_signature,
        )

    try:
        result = await asyncio.to_thread(_do)
    except PaymentRequired as exc:
        return _payment_required(exc)
    except X402PaymentRequired as exc:
        return _x402_payment_required(exc)
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
    if name == "macaroons_categories":
        return await _public_registry_document("/api/public/taxonomy")
    if name == "macaroons_discover_mcp":
        return await _public_registry_document("/api/public/mcp-servers")
    if name == "macaroons_sources":
        return await _public_registry_document("/api/public/sources")
    if name == "macaroons_purchase":
        return _error("legacy Bitcoin/Lightning purchasing is not exposed; use x402 products")
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
        version="0.4.0",
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
