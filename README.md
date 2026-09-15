# macaroonnetwork-mcp

<!-- mcp-name: com.macaroonnetwork/mcp-server -->

MCP discovery router for [Macaroon Network](https://macaroonnetwork.com), a
marketplace where agents find evidence-backed products and pay per successful
query.

The payment rail exposed by this release is **x402 using USDC on Base
mainnet**. The package never holds a wallet or signs a payment. It returns the
exact x402 challenge for the caller's own wallet infrastructure to sign, then
accepts that signed proof on the retry.

## Tools

- **`macaroons_search`** — search sale-ready products by natural-language
  intent. Free.
- **`macaroons_metadata`** — retrieve free freshness and content-hash metadata
  for a feed target.
- **`macaroons_categories`** — retrieve the canonical category registry and
  exact mapped-product counts. Free.
- **`macaroons_discover_mcp`** — retrieve evidenced live Macaroon MCP servers
  and their transports. Free.
- **`macaroons_sources`** — retrieve reviewed source and rights records, with
  explicit partial-coverage reporting. Free.
- **`macaroons_execute`** — execute an x402 USDC product and receive the
  predicate-verified result and receipt.

## Paying with x402

When a product needs payment, `macaroons_execute` returns an
`x402_payment_required` result instead of hiding the challenge:

```json
{
  "x402_payment_required": true,
  "resource_url": "https://api.macaroonnetwork.com/execute/...",
  "amount_atomic": "3000",
  "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  "network": "eip155:8453",
  "pay_to": "0x33cc...",
  "extra_name": "USD Coin",
  "extra_version": "2",
  "max_timeout_seconds": 60,
  "x402_version": 2
}
```

Sign the exact payment described by the challenge with your own wallet or
Coinbase CDP infrastructure. Then call `macaroons_execute` again with identical
arguments plus `payment_signature`. x402 exact settlement uses one signed
retry; there is no invoice-polling flow.

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

The default registry is `https://api.macaroonnetwork.com`. For local
development, override it with `MACAROONS_REGISTRY_URL`.

## License

MIT
