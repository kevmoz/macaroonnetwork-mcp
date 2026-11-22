# Macaroon Network — Verifiable commerce for AI agents

<!-- mcp-name: com.macaroonnetwork/mcp-server -->

**Discover → Inspect → Pay → Verify → Settle.**

Macaroon Network gives AI agents a machine-readable way to discover digital
services, inspect their inputs, price, source information and declared
acceptance conditions, then decide whether to execute.

For predicate-gated routes, Macaroon evaluates the declared machine-checkable
condition against the returned result as part of settlement. An HTTP 200 alone
does not prove that the acceptance condition passed or that payment settled.
See [how acceptance predicates work](docs/acceptance-predicates.md).
Read the [worked example on HTTP 200 and agent payments](https://macaroonnetwork.com/articles/http-200-agent-payments?utm_source=github&utm_medium=referral&utm_campaign=http200-agent-payments).

**[Try free discovery](docs/wallet-free-quickstart.md) — no wallet or API key required.**

- Website: https://macaroonnetwork.com
- [Service catalogue](https://macaroonnetwork.com/services?utm_source=github&utm_medium=referral&utm_campaign=public_mcp)
- [Developer docs](https://macaroonnetwork.com/developers?utm_source=github&utm_medium=referral&utm_campaign=public_mcp)
- Remote MCP: `https://api.macaroonnetwork.com/mcp`
- AI catalogue: `https://api.macaroonnetwork.com/.well-known/ai-catalog.json`
- Agent capabilities: `https://api.macaroonnetwork.com/.well-known/agent-capabilities`
- A2A Agent Card: `https://api.macaroonnetwork.com/.well-known/agent-card.json`
- x402 discovery: `https://api.macaroonnetwork.com/.well-known/x402`
- OpenAPI: `https://api.macaroonnetwork.com/openapi.json`

## Try the wallet-free path first

Connect your MCP client to:

```text
https://api.macaroonnetwork.com/mcp
```

Then call:

1. `macaroons_categories` — inspect the category registry.
2. `macaroons_search` — search for a capability such as live UK company data.
3. Inspect the returned listing before considering execution.

Example search arguments:

```json
{
  "intent": "Find a live UK Companies House company search",
  "limit": 3
}
```

This discovery path does not require payment.

## Current public MCP tools

The current 0.4.0 server exposes:

- **`macaroons_search`** — search sale-ready products by natural-language intent.
- **`macaroons_metadata`** — retrieve freshness and content-hash metadata.
- **`macaroons_categories`** — retrieve canonical categories and mapped-product counts.
- **`macaroons_discover_mcp`** — discover evidenced Macaroon MCP servers and transports.
- **`macaroons_sources`** — inspect reviewed sources and rights records.
- **`macaroons_execute`** — request execution for a selected service.

The first five are discovery/read-oriented. Paid terms are route-specific and
must be taken from the selected listing and current unsigned challenge.

## x402 payment model

Selected paid routes use **x402 with USDC on Base mainnet**.

The package does not hold a wallet and does not sign for the caller. When a
route requires payment, `macaroons_execute` returns the exact challenge for the
caller's wallet infrastructure to sign. The caller then retries with the signed
proof.

Example challenge shape:

```json
{
  "x402_payment_required": true,
  "resource_url": "https://api.macaroonnetwork.com/execute/...",
  "amount_atomic": "3000",
  "network": "eip155:8453",
  "extra_name": "USD Coin",
  "extra_version": "2",
  "x402_version": 2
}
```

Do not assume every service uses identical payment or failure semantics. Inspect
the individual service contract before execution.

## Install the stdio package

```bash
pip install macaroonnetwork-mcp
```

Generic stdio configuration:

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

## Remote MCP client examples

### Claude Code

```bash
claude mcp add --transport http macaroon-network https://api.macaroonnetwork.com/mcp
```

### Codex CLI

```bash
codex mcp add macaroon-network --url https://api.macaroonnetwork.com/mcp
```

### Cursor

See [client-configs/cursor.json](client-configs/cursor.json).

### VS Code

See [client-configs/vscode.json](client-configs/vscode.json).

Client-specific account, connector and policy requirements can apply.

## Raw Streamable HTTP example

See [docs/wallet-free-quickstart.md](docs/wallet-free-quickstart.md) for a
minimal JSON-RPC walkthrough that initializes the server, lists tools and calls
`macaroons_categories` without a wallet.

## Why Macaroon is different

Most tool directories tell an agent **where an API exists**.

Macaroon is designed to make the commercial contract inspectable too:

- machine-readable inputs
- price
- source/provenance information
- declared acceptance condition
- route-specific payment terms
- explicit limitations

The core idea is simple:

> Agents should pay for checked outcomes, not merely successful HTTP responses.

## Press kit

See the [press kit](docs/press-kit.md) for the public demo, technical context and artwork.

## Security

Please do not report security issues in a public issue. See
[SECURITY.md](SECURITY.md) or https://macaroonnetwork.com/.well-known/security.txt.

## License

The Python package metadata declares MIT. A root LICENSE file will only be added
after the repository owner completes the explicit public-release licence review.
