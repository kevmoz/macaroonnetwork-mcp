"""MacaroonClient — buyer SDK, vendored from packages/buyer/client.py in the
macaroonnetwork repo for standalone distribution (see that file for the
canonical, gate-tested version this tracks).

Two differences from the reference implementation, both because this file
ships to machines that are not a checkout of that repo:

1. No "docker-regtest" payment mode -- there is no bundled regtest LND here
   to shell out to. Only "external" (a real LND node you configure) and
   "none" (honest passthrough) exist.
2. MACAROONS_BUYER_LND_MODE defaults to "none" here, not "docker-regtest".
   That is the only safe default for an arbitrary external install.

discover() -> metadata() -> commit(predicate) -> purchase(): the SDK talks
to the registry for discovery, to the feed API's free /meta for the
pre-purchase commitment, and to the hold-invoice-based
POST /pricing/changes/purchase for the actual money-moving step. It never
holds a private key or wallet credential itself -- see MacaroonClient's
payment-mode docstring below for exactly what "none" and "external" mean.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from .exceptions import (
    LndPaymentError,
    PaymentRequired,
    PayloadTampered,
    PredicateNotSatisfied,
    ReceiptMismatch,
    SpendCapExceeded,
    X402ChallengeMalformed,
    X402PaymentRequired,
)
from . import predicate as predicate_lib

_CHALLENGE_RE = re.compile(r'(\w+)="([^"]*)"')

# Who actually pays the BOLT11 invoice on a 402. Opt-in only; default is the
# honest one for an arbitrary external install:
#
# - "none" (default): no auto-pay attempted. purchase()/execute_capability()
#   raise PaymentRequired(macaroon, bolt11) so the caller can pay with
#   whatever Lightning wallet they actually have, then retry with
#   resume_macaroon set to resume the SAME hold (see purchase()'s
#   docstring for why a plain retry would be wrong).
# - "external": shells to a real `lncli` binary pointed at a real LND node
#   via LND_BUYER_HOST/LND_BUYER_TLS/LND_BUYER_MACAROON, for an operator
#   who has their own real LND node and wants this client to auto-pay
#   from it.
_BUYER_LND_MODES = {"external", "none"}


def _buyer_lnd_mode() -> str:
    return os.environ.get("MACAROONS_BUYER_LND_MODE", "none").strip().lower()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise LndPaymentError(f"external buyer LND mode requires {name}")
    return value


def _parse_www_authenticate(header: str) -> dict[str, str]:
    return dict(_CHALLENGE_RE.findall(header))


def _parse_payment_required_header(headers: dict[str, str]) -> dict[str, Any] | None:
    """Real x402 challenges arrive as a base64-encoded JSON body in a
    payment-required header (confirmed live against api.macaroonnetwork.com
    -- never raw JSON, unlike L402's plain www-authenticate string). Header
    lookup is case-insensitive by hand rather than relying on the caller's
    headers mapping already being a case-insensitive dict, since real
    requests.Response.headers is one but a plain test double dict isn't.

    Returns None only when no payment-required header is present at all --
    a header that IS present but fails to decode/parse is a real protocol
    bug and raises X402ChallengeMalformed, never silently treated the same
    as "no challenge"."""
    raw = None
    for key, value in headers.items():
        if key.lower() == "payment-required":
            raw = value
            break
    if raw is None:
        return None

    try:
        decoded_bytes = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise X402ChallengeMalformed(f"payment-required header is not valid base64: {exc}") from exc
    try:
        challenge = json.loads(decoded_bytes)
    except json.JSONDecodeError as exc:
        raise X402ChallengeMalformed(f"decoded payment-required header is not valid JSON: {exc}") from exc

    accepts = challenge.get("accepts")
    if not isinstance(accepts, list) or not accepts or not isinstance(accepts[0], dict):
        raise X402ChallengeMalformed("decoded challenge has no usable accepts[0] entry")

    return challenge


def _canonical_json_hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Commitment:
    target_id: str
    predicate: dict[str, Any]
    predicate_hash: str
    metadata_content_hash: str | None


class MacaroonClient:
    def __init__(
        self,
        registry_url: str,
        feed_url: str,
        max_spend_msat: int = 10_000,
        price_msat: int = 1000,
    ):
        self.registry_url = registry_url.rstrip("/")
        self.feed_url = feed_url.rstrip("/")
        self.max_spend_msat = max_spend_msat
        # The client's own known/quoted price, used ONLY to check the spend
        # cap before making any network call at all — the server's 402
        # response already implies an invoice has been minted, which is too
        # late to check a cap against.
        self.price_msat = price_msat
        self.spent_msat = 0

    def discover(self) -> list[dict[str, Any]]:
        resp = requests.get(f"{self.registry_url}/.well-known/agent-capabilities", timeout=15)
        resp.raise_for_status()
        return resp.json().get("listings", [])

    def get_listing(self, capability_id: str) -> dict[str, Any]:
        resp = requests.get(f"{self.registry_url}/listings/{capability_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def metadata(self, target_id: str) -> dict[str, Any]:
        resp = requests.get(f"{self.feed_url}/meta", timeout=15)
        resp.raise_for_status()
        for target in resp.json().get("targets", []):
            if target["target_id"] == target_id:
                return target
        raise ValueError(f"unknown target_id: {target_id}")

    def commit(self, meta: dict[str, Any], predicate: dict[str, Any]) -> Commitment:
        """Local only — no network call. Validates the predicate against the
        same grammar the server will evaluate against and computes its
        canonical hash so the client commits to the exact same value the
        server will bind into the macaroon."""
        predicate_lib.evaluate(predicate, {}, datetime.now(timezone.utc))
        return Commitment(
            target_id=meta["target_id"],
            predicate=predicate,
            predicate_hash=predicate_lib.predicate_hash(predicate),
            metadata_content_hash=meta.get("content_hash"),
        )

    def _pay_invoice_background(self, bolt11: str) -> subprocess.Popen:
        mode = _buyer_lnd_mode()
        if mode == "external":
            cmd = [
                os.environ.get("MACAROONS_LNCLI_BIN", os.environ.get("LNCLI_BIN", "lncli")),
                f"--network={os.environ.get('MACAROONS_LND_NETWORK', 'mainnet')}",
                f"--rpcserver={_required_env('LND_BUYER_HOST')}",
                f"--tlscertpath={_required_env('LND_BUYER_TLS')}",
                f"--macaroonpath={_required_env('LND_BUYER_MACAROON')}",
                "payinvoice", "--force", "--json", bolt11,
            ]
            return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raise LndPaymentError(
            f"_pay_invoice_background called with MACAROONS_BUYER_LND_MODE={mode!r} -- "
            "callers must check for 'none' and raise PaymentRequired before this point"
        )

    def purchase(
        self,
        commitment: Commitment,
        since: str,
        limit: int = 100,
        poll_attempts: int = 10,
        poll_delay_seconds: float = 1.0,
        resume_macaroon: str | None = None,
    ) -> dict[str, Any]:
        """resume_macaroon: skip minting a new hold and go straight to
        polling/resolving an EXISTING one -- the macaroon a prior
        PaymentRequired handed back, after the caller paid that invoice
        with their own wallet. A plain re-call with resume_macaroon=None
        would mint a brand-new hold instead of resuming the one just paid,
        orphaning it until it times out and refunds on its own."""
        if self.spent_msat + self.price_msat > self.max_spend_msat:
            raise SpendCapExceeded(self.price_msat, self.max_spend_msat, self.spent_msat)

        body = {
            "predicate": commitment.predicate,
            "target_id": commitment.target_id,
            "since": since,
            "limit": limit,
        }
        url = f"{self.feed_url}/pricing/changes/purchase"

        if resume_macaroon is not None:
            result = self._retry_until_resolved(
                url, body, resume_macaroon, poll_attempts, poll_delay_seconds
            )
            return self._finish(result, commitment)

        resp = requests.post(url, json=body, timeout=15)

        if resp.status_code == 200:
            # L402_ENABLED=false — no payment step at all.
            result = resp.json()
        elif resp.status_code == 402:
            challenge = _parse_www_authenticate(resp.headers.get("www-authenticate", ""))
            macaroon = challenge.get("macaroon")
            bolt11 = challenge.get("invoice")
            if not macaroon or not bolt11:
                resp.raise_for_status()
            if _buyer_lnd_mode() == "none":
                raise PaymentRequired(macaroon, bolt11, self.price_msat)
            pay_proc = self._pay_invoice_background(bolt11)
            try:
                result = self._retry_until_resolved(
                    url, body, macaroon, poll_attempts, poll_delay_seconds
                )
            finally:
                pay_proc.wait(timeout=30)
        else:
            resp.raise_for_status()
            raise RuntimeError(f"unexpected status with no error raised: {resp.status_code}")

        return self._finish(result, commitment)

    def _retry_until_resolved(
        self,
        url: str,
        body: dict,
        macaroon: str,
        poll_attempts: int,
        poll_delay_seconds: float,
        request_timeout_seconds: float = 15,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"L402 {macaroon}"}
        for _ in range(poll_attempts):
            resp = requests.post(
                url, json=body, headers=headers, timeout=request_timeout_seconds
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 402:
                detail = resp.json()
                if detail.get("reason") == "not_yet_accepted":
                    time.sleep(poll_delay_seconds)
                    continue
            resp.raise_for_status()
            raise RuntimeError(f"unexpected status with no error raised: {resp.status_code}")
        raise TimeoutError("hold invoice never reached ACCEPTED within the retry budget")

    def _finish(self, result: dict[str, Any], commitment: Commitment) -> dict[str, Any]:
        if not result["predicate_passed"]:
            raise PredicateNotSatisfied(result["receipt"]["predicate_hash"])

        if result.get("settled"):
            self.spent_msat += self.price_msat

        # Independent re-check: fetch /meta again, fresh, rather than trust
        # the paid response's own self-reported content_hash.
        current_meta = self.metadata(commitment.target_id)
        actual_hash = current_meta.get("content_hash")
        if commitment.metadata_content_hash is not None and actual_hash != commitment.metadata_content_hash:
            raise PayloadTampered(commitment.metadata_content_hash, actual_hash)

        return {"payload": result["payload"], "receipt": result["receipt"]}

    def execute_capability(
        self,
        capability_id: str,
        input_payload: dict[str, Any],
        predicate: dict[str, Any] | None = None,
        *,
        max_spend_sats: int | None = None,
        poll_attempts: int = 10,
        poll_delay_seconds: float = 1.0,
        resume_macaroon: str | None = None,
        payment_signature: str | None = None,
    ) -> dict[str, Any]:
        """resume_macaroon: see purchase()'s docstring -- same reasoning,
        same requirement to resume rather than re-mint after a
        PaymentRequired the caller has since paid out of band.

        payment_signature: the x402 analogue of resume_macaroon. This
        client never holds a wallet/signing credential for x402 any more
        than it does for L402 (see X402PaymentRequired's docstring) -- on
        a real x402 challenge with no payment_signature supplied, it raises
        X402PaymentRequired carrying the real accepts[0] terms so the
        caller can sign with their own wallet infra and retry with
        payment_signature set to the resulting proof. Unlike L402's
        hold-invoice accept/poll cycle, x402's "exact" scheme settles
        synchronously within one request, so this is a single retry with a
        PAYMENT-SIGNATURE header, never _retry_until_resolved()'s polling
        loop."""
        if not isinstance(input_payload, dict):
            raise ValueError("input_payload must be a dict")

        listing = self.get_listing(capability_id)
        price_msat = int(listing["price_sats"]) * 1000
        if max_spend_sats is not None and price_msat > max_spend_sats * 1000:
            raise SpendCapExceeded(price_msat, max_spend_sats * 1000, self.spent_msat)
        if self.spent_msat + price_msat > self.max_spend_msat:
            raise SpendCapExceeded(price_msat, self.max_spend_msat, self.spent_msat)

        effective_predicate = predicate or listing.get("sample_predicate")
        if not effective_predicate:
            raise ValueError(f"listing {capability_id} has no sample_predicate")
        predicate_lib.evaluate(effective_predicate, {}, datetime.now(timezone.utc))

        body = {"input": input_payload, "predicate": effective_predicate}
        url = f"{self.registry_url}/execute/{capability_id}"
        timeout_seconds = self._execute_request_timeout_seconds(listing)

        if resume_macaroon is not None:
            result = self._retry_until_resolved(
                url, body, resume_macaroon, poll_attempts, poll_delay_seconds,
                request_timeout_seconds=timeout_seconds,
            )
            return self._finish_execute(
                result, capability_id=capability_id, input_payload=input_payload,
                predicate=effective_predicate, price_msat=price_msat,
            )

        if payment_signature is not None:
            resp = requests.post(
                url, json=body, headers={"PAYMENT-SIGNATURE": payment_signature},
                timeout=timeout_seconds,
            )
            if resp.status_code != 200:
                resp.raise_for_status()
                raise RuntimeError(f"unexpected status with no error raised: {resp.status_code}")
            return self._finish_execute(
                resp.json(), capability_id=capability_id, input_payload=input_payload,
                predicate=effective_predicate, price_msat=price_msat,
            )

        resp = requests.post(url, json=body, timeout=timeout_seconds)
        if resp.status_code == 200:
            result = resp.json()
        elif resp.status_code == 402:
            challenge = _parse_www_authenticate(resp.headers.get("www-authenticate", ""))
            macaroon = challenge.get("macaroon")
            bolt11 = challenge.get("invoice")
            if macaroon and bolt11:
                if _buyer_lnd_mode() == "none":
                    raise PaymentRequired(macaroon, bolt11, price_msat)
                pay_proc = self._pay_invoice_background(bolt11)
                try:
                    result = self._retry_until_resolved(
                        url,
                        body,
                        macaroon,
                        poll_attempts,
                        poll_delay_seconds,
                        request_timeout_seconds=timeout_seconds,
                    )
                finally:
                    pay_proc.wait(timeout=30)
            else:
                x402_challenge = _parse_payment_required_header(resp.headers)
                if x402_challenge is None:
                    resp.raise_for_status()
                    raise RuntimeError("402 response with neither an L402 nor an x402 challenge")
                accept = x402_challenge["accepts"][0]
                raise X402PaymentRequired(
                    resource_url=(x402_challenge.get("resource") or {}).get("url", url),
                    amount_atomic=accept["amount"],
                    asset=accept["asset"],
                    network=accept["network"],
                    pay_to=accept["payTo"],
                    extra_name=(accept.get("extra") or {}).get("name", ""),
                    extra_version=(accept.get("extra") or {}).get("version", ""),
                    max_timeout_seconds=accept.get("maxTimeoutSeconds", 60),
                    x402_version=x402_challenge.get("x402Version", 2),
                )
        else:
            resp.raise_for_status()
            raise RuntimeError(f"unexpected status with no error raised: {resp.status_code}")

        return self._finish_execute(
            result,
            capability_id=capability_id,
            input_payload=input_payload,
            predicate=effective_predicate,
            price_msat=price_msat,
        )

    def _execute_request_timeout_seconds(self, listing: dict[str, Any]) -> float:
        policy = listing.get("policy") or {}
        value = policy.get("response_timeout_seconds", 15)
        if isinstance(value, bool):
            return 15
        try:
            bridge_timeout = float(value)
        except (TypeError, ValueError):
            return 15
        if bridge_timeout <= 0:
            return 15
        return min(max(15.0, bridge_timeout + 5.0), 930.0)

    def _finish_execute(
        self,
        result: dict[str, Any],
        *,
        capability_id: str,
        input_payload: dict[str, Any],
        predicate: dict[str, Any],
        price_msat: int,
    ) -> dict[str, Any]:
        receipt = result.get("receipt") or {}
        expected_predicate_hash = predicate_lib.predicate_hash(predicate)
        expected_input_hash = _canonical_json_hash(input_payload)

        self._require_receipt_value(receipt, "capability_id", capability_id)
        self._require_receipt_value(receipt, "predicate_hash", expected_predicate_hash)
        self._require_receipt_value(receipt, "input_hash", expected_input_hash)

        if not result["predicate_passed"]:
            raise PredicateNotSatisfied(receipt.get("predicate_hash"))

        payload = result["payload"]
        expected_output_hash = receipt.get("output_hash")
        if expected_output_hash is not None:
            actual_output_hash = _canonical_json_hash(payload)
            if actual_output_hash != expected_output_hash:
                raise PayloadTampered(expected_output_hash, actual_output_hash)

        if result.get("settled"):
            self.spent_msat += price_msat

        return {"payload": payload, "receipt": receipt}

    def _require_receipt_value(
        self, receipt: dict[str, Any], field: str, expected: str
    ) -> None:
        actual = receipt.get(field)
        if actual != expected:
            raise ReceiptMismatch(field, expected, actual)
