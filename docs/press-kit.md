# Macaroon Network press kit

**Verifiable commerce for AI agents**

Macaroon Network lets agents discover digital services and inspect their
inputs, source, price and declared acceptance conditions before choosing
whether to execute. Free discovery uses public MCP and needs no Macaroon
account, API key, or wallet. Applicable paid routes use x402 with USDC on Base.
For predicate-gated routes, Macaroon checks the actual result against the
declared condition as part of settlement.

## Reproduce the free demo

Run the [wallet-free quickstart](wallet-free-quickstart.md). It connects to
`https://api.macaroonnetwork.com/mcp`, lists categories, and searches for the
[Live UK Company Search contract](https://macaroonnetwork.com/listings/companies-house-live-search-v1).
Inspect its source, inputs, current price and predicate. The walkthrough ends
before execution. See [why HTTP 200 is not enough](why-http-200-isnt-enough.md)
for the difference between transport success, an outcome check and settlement.

## Downloadable visuals

- [Public Macaroon logo](press-assets/public-logo.png)
- [Discover → Inspect → Pay → Verify → Settle](press-assets/01-commerce-flow.png)
- [HTTP 200 is not enough](press-assets/02-http-200.png)
- [Wallet-free demo capture](press-assets/03-wallet-free-demo.png) and [original stdout](press-assets/demo-output.txt)
- [Companies House example](press-assets/04-companies-house.png)
- [Acceptance predicate](press-assets/05-predicate.png)
- [x402 payment terms](press-assets/06-x402-flow.png)
- [Public discovery surfaces](press-assets/07-ecosystem.png)

The demo image renders captured terminal output from a public protocol check.
It does not represent buyer usage or a paid transaction.

[Website](https://macaroonnetwork.com) · [Developer docs](https://macaroonnetwork.com/developers) ·
[Public source](https://github.com/kevmoz/macaroonnetwork-mcp) ·
[Business contact](mailto:hello@macaroonnetwork.com)
