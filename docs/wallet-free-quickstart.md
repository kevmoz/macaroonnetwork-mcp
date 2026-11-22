# Wallet-free remote MCP quickstart

This walkthrough uses the public Streamable HTTP endpoint:

`https://api.macaroonnetwork.com/mcp`

It performs discovery only. It does not call paid execution and does not require
a wallet, API key or signing material.

## Run the free demo

From this repository, run:

```sh
python examples/free_companies_house_search.py
```

The example prints matching capabilities and the public contract URL. For
an interactive client or a raw JSON-RPC walkthrough, use the steps below.

## 1. Initialize

```bash
curl --silent --show-error --include \
  https://api.macaroonnetwork.com/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"initialize",
    "params":{
      "protocolVersion":"2025-03-26",
      "capabilities":{},
      "clientInfo":{"name":"macaroon-quickstart","version":"1"}
    }
  }'
```

Use the protocol version returned by the server. If the response includes an
`Mcp-Session-Id`, retain it for subsequent requests.

## 2. Notify initialized

Use the negotiated version in the `MCP-Protocol-Version` header. If the server
issued `Mcp-Session-Id`, set `mcp_session_id` to that value before running this
Bash block. Subsequent responses can be JSON or an SSE `data:` line.

```bash
mcp_headers=(-H 'Content-Type: application/json'
  -H 'Accept: application/json, text/event-stream'
  -H 'MCP-Protocol-Version: 2025-03-26') # Replace with the returned version.
if [[ -n "${mcp_session_id:-}" ]]; then
  mcp_headers+=(-H "Mcp-Session-Id: $mcp_session_id")
fi
mcp_rpc() {
  curl --silent --show-error --include --max-time 20     https://api.macaroonnetwork.com/mcp "${mcp_headers[@]}" --data "$1"
}
mcp_rpc '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

Pass each JSON body in the next three steps as a single quoted argument to
`mcp_rpc`.

## 3. List tools

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

## 4. Call a free discovery tool

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "macaroons_categories",
    "arguments": {}
  }
}
```

## 5. Search for a real capability

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "macaroons_search",
    "arguments": {
      "intent": "Find a live UK Companies House company search",
      "limit": 3
    }
  }
}
```

## 6. Inspect the contract and stop

Open [Live UK Company Search](https://macaroonnetwork.com/listings/companies-house-live-search-v1?utm_source=github&utm_medium=referral&utm_campaign=public_mcp).
Inspect the input schema, Companies House provenance, advertised price and
acceptance predicate. See [what that predicate checks](acceptance-predicates.md).

This completes the demo. The walkthrough ends before `macaroons_execute` and
requires no Macaroon signup, email, wallet or payment.

[Why HTTP 200 isn't enough when agents spend money](why-http-200-isnt-enough.md)
