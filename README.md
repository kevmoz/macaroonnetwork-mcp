# macaroonnetwork-mcp

<!-- mcp-name: com.macaroonnetwork/mcp-server -->

MCP client for [Macaroon Network](https://macaroonnetwork.com) — a
marketplace where AI agents discover, pay for (Bitcoin/Lightning via L402),
and buy live data.

## What this does

Four tools:

- **`macaroons_search`** — semantic search over the live marketplace registry
  by natural-language intent. Free.
- **`macaroons_metadata`** — free freshness/content-hash metadata for a feed
  target, before deciding whether to buy. Free.
- **`macaroons_purchase`** / **`macaroons_execute`** — pay via Lightning L402
  and receive the real, predicate-verified result. See "Paying" below —
  by default this package holds no wallet and doesn't attempt payment for you.

## Paying

This package never holds a private key or wallet credential by default.
When a purchase/execute call needs payment, it returns a `payment_required`
result instead of failing:

```json
{
  "payment_required": true,
  "invoice": "lnbc...",
  "macaroon": "eyJ...",
  "amount_msat": 250000,
  "instructions": "Pay this BOLT11 invoice with your own Lightning wallet, then call this same tool again with identical arguments PLUS resume_macaroon set to the macaroon above."
}
```

Pay the invoice with whatever Lightning wallet you actually have, then call
the same tool again with `resume_macaroon` set to the macaroon above. A
plain retry *without* `resume_macaroon` mints a brand-new invoice instead of
resuming the one you just paid — always pass it back.

If you run your own real LND node and want this package to auto-pay from
it instead of returning `payment_required`, set:

```bash
MACAROONS_BUYER_LND_MODE=external
LND_BUYER_HOST=your-node:10009
LND_BUYER_TLS=/path/to/tls.cert
LND_BUYER_MACAROON=/path/to/admin.macaroon
```

This shells out to a real `lncli` binary on your machine — install LND's
`lncli` separately, it isn't bundled here.

## Install

```bash
pip install macaroonnetwork-mcp
```

## Use with an MCP client

```json
{
  "mcpServers": {
    "macaroonnetwork": {
      "command": "macaroonnetwork-mcp"
    }
  }
}
```

Talks to `https://api.macaroonnetwork.com` by default. Override with
`MACAROONS_REGISTRY_URL` / `MACAROONS_FEED_URL` env vars to point at a local
dev stack instead. `MACAROONS_SESSION_BUDGET_SATS` (default 1000) caps total
spend per server process; each tool call also takes a `max_spend_sats`
per-call cap (default 100).

## License

MIT
