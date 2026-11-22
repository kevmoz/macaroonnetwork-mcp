"""Run the public Macaroon discovery demo with Python 3."""
import json
from urllib.request import Request, urlopen

ENDPOINT = "https://api.macaroonnetwork.com/mcp"
LISTING = "https://macaroonnetwork.com/listings/companies-house-live-search-v1"
INTENT = "Find a live UK Companies House company search"


def rpc(headers, method, request_id=None, params=None):
    body = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        body["id"] = request_id
    if params is not None:
        body["params"] = params

    request = Request(ENDPOINT, data=json.dumps(body).encode(), headers=headers)
    with urlopen(request, timeout=20) as response:
        if request_id is None:
            if response.status != 202:
                raise RuntimeError("The server did not accept the initialized notification.")
            return None, response.headers
        payload = response.read().decode()
        if response.headers.get_content_type() == "text/event-stream":
            for line in payload.splitlines():
                if line.startswith("data:"):
                    message = json.loads(line[5:].strip())
                    if message.get("id") == request_id:
                        break
            else:
                raise RuntimeError(f"No response for {method}.")
        else:
            message = json.loads(payload)
        result = message.get("result")
        if message.get("id") != request_id or not isinstance(result, dict) or result.get("isError"):
            raise RuntimeError(f"{method} failed.")
        return result, response.headers


def main():
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    initialized, response_headers = rpc(headers, "initialize", 1, {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "macaroon-free-demo", "version": "1"},
    })
    headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
    session_id = response_headers.get("Mcp-Session-Id")
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    rpc(headers, "notifications/initialized")

    tools, _ = rpc(headers, "tools/list", 2)
    names = {tool["name"] for tool in tools["tools"]}
    if not {"macaroons_categories", "macaroons_search"} <= names:
        raise RuntimeError("The discovery tools are unavailable.")
    print("Connected. Discovery tools are available.")
    rpc(headers, "tools/call", 3, {"name": "macaroons_categories", "arguments": {}})
    print("Categories returned successfully.")
    matches, _ = rpc(headers, "tools/call", 4, {
        "name": "macaroons_search",
        "arguments": {"intent": INTENT, "limit": 3},
    })
    records = matches.get("structuredContent")
    if isinstance(records, dict):
        records = records.get("result")
    if records is None:
        records = [
            record
            for item in matches.get("content", [])
            if item.get("type") == "text"
            for record in json.loads(item["text"])
        ]
    if not any(record.get("service_id") == "companies-house-live-search-v1" for record in records):
        raise RuntimeError("Live UK Company Search was not among the returned capabilities.")
    for record in records:
        print(f"- {record['name']}")
    print(f"\nInspect inputs, source, price and acceptance condition: {LISTING}")


if __name__ == "__main__":
    main()
