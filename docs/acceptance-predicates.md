# Acceptance predicates

An acceptance predicate is a condition declared in a service contract. For a
predicate-gated route, Macaroon evaluates the condition against the actual
returned result. The condition passes when the result meets the listed checks.
A passing condition is required for predicate-gated settlement. Confirm
settlement from the outcome and receipt for that route. An HTTP success code
only describes the HTTP response.

## Public example

The [Live UK Company Search listing](https://macaroonnetwork.com/listings/companies-house-live-search-v1)
declares a conjunction: at least one item in `records`, plus provenance flags
for metadata-only delivery, live data and outbound network use. All four
conditions must pass. An empty result fails the count check. The flags describe
the returned result's provenance. These checks do not establish that a match is
the intended company or certify the completeness of its records.

The listing exposes the current predicate, predicate hash, input schema and
price. Which checks apply, how a failed attempt is reported, and how payment
is handled depend on the route and rail. The
[wallet-free quickstart](wallet-free-quickstart.md) stops after inspecting the
contract.
