# Why HTTP 200 Isn't Enough When AI Agents Spend Money

An agent has found a company-search API. The server answered HTTP 200. Can the
agent tell whether it received a current Companies House record, whether the
response met the service contract, or whether payment settled? The status code
alone answers none of those questions.

## From discovery to a checked result

Discovery gives the agent a way to find a capability. A useful listing gives it
the next decision: what inputs does the service accept, where does the data come
from, what will it cost, and which properties can be checked on the output?

The payment challenge gives the agent the terms of a particular request. On
applicable Macaroon routes, x402 challenges specify terms for USDC on Base. An
unsigned challenge shows the terms offered. A settlement claim needs evidence
for the actual paid execution and its receipt.

For predicate-gated routes, Macaroon evaluates a declared acceptance condition
against the actual result as part of settlement. Acceptance and settlement are
distinct facts: the checks can pass while settlement still needs its own
confirmation. Inspect the route contract for failure handling and payment terms.

## Try a real contract without paying

Run the [free MCP demo](wallet-free-quickstart.md). Connect to the public endpoint,
list categories, then search for **Find a live UK Companies House company
search**. Open the [Live UK Company Search listing](https://macaroonnetwork.com/listings/companies-house-live-search-v1)
and compare the input schema, source, price, and predicate.

The displayed predicate requires at least one returned record and checks three
provenance flags: metadata-only delivery, live data, and outbound network use.
An empty result fails the count check. Those checks cover properties of the
response. Whether the record is the company you meant still depends on the
search inputs and how you identify the match.

This walkthrough verifies free discovery and public contract inspection. It
ends before paid execution, so it supplies no settlement evidence. You can
repeat it without a Macaroon account, API key, or wallet.

[Try free MCP discovery](wallet-free-quickstart.md)
