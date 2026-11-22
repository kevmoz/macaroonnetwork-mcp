# Wallet-free remote MCP quickstart

This walkthrough uses the public Streamable HTTP endpoint:

`https://api.macaroonnetwork.com/mcp`

It performs discovery only. It does not call paid execution and does not require
a wallet, API key or signing material.

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

Send `notifications/initialized` using the negotiated protocol version and,
when issued, the session ID.

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

Treat search results as discovery pointers. Inspect the selected listing and its
current contract before execution.

The paid `macaroons_execute` path is intentionally outside this quickstart.
