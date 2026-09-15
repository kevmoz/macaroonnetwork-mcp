"""Buyer SDK exceptions (see specs/B4.1-buyer-sdk.md)."""
from __future__ import annotations


class SpendCapExceeded(Exception):
    """Raised BEFORE any invoice is paid — a cap violation never costs sats."""

    def __init__(self, attempted_msat: int, cap_msat: int, spent_so_far_msat: int):
        self.attempted_msat = attempted_msat
        self.cap_msat = cap_msat
        self.spent_so_far_msat = spent_so_far_msat
        super().__init__(
            f"purchase would spend {attempted_msat}msat "
            f"(spent {spent_so_far_msat}/{cap_msat}msat this session)"
        )


class PayloadTampered(Exception):
    """The delivered payload's hash != the pre-purchase metadata content_hash
    quoted by the free /meta call — the buyer's own tamper check, independent
    of the server's predicate verdict (see S2.3's spec for why this exists)."""

    def __init__(self, expected_hash: str, actual_hash: str):
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(f"payload hash mismatch: expected {expected_hash}, got {actual_hash}")


class PredicateNotSatisfied(Exception):
    """The server evaluated the predicate against the real payload and it
    failed — the hold invoice was cancelled and the buyer's sats refunded."""

    def __init__(self, predicate_hash: str):
        self.predicate_hash = predicate_hash
        super().__init__(f"predicate did not pass; invoice refunded (predicate_hash={predicate_hash})")


class ReceiptMismatch(Exception):
    """A paid execute receipt did not bind to the capability/input/predicate
    the buyer submitted."""

    def __init__(self, field: str, expected: str | None, actual: str | None):
        self.field = field
        self.expected = expected
        self.actual = actual
        super().__init__(f"receipt {field} mismatch: expected {expected}, got {actual}")


class LndPaymentError(Exception):
    """The buyer's own LND node failed to pay the hold invoice."""


class PaymentRequired(Exception):
    """No buyer-side auto-pay is configured (MACAROONS_BUYER_LND_MODE=none,
    the honest default for anyone who isn't this repo's own regtest gates).
    Carries the hold invoice + macaroon back to the caller so THEY can pay
    it with whatever wallet they actually have and retry -- see
    packages/settlement/lnd.py's pay_invoice_background() docstring:
    "production buyers pay the returned BOLT11 invoice from their own
    node." This is that contract surfaced as a catchable result instead of
    a crash."""

    def __init__(self, macaroon: str, bolt11: str, amount_msat: int | None = None):
        self.macaroon = macaroon
        self.bolt11 = bolt11
        self.amount_msat = amount_msat
        super().__init__(f"payment required: pay {bolt11} then retry with the L402 macaroon")


class X402ChallengeMalformed(Exception):
    """A response carried a payment-required header, but it wasn't valid
    base64, valid JSON once decoded, or was missing a usable accepts[0]
    entry. This is a real protocol-level bug (a broken/incompatible seller,
    or an x402 spec change) -- it must never be silently treated as "no
    challenge present"."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"malformed x402 payment-required challenge: {reason}")


class X402PaymentRequired(Exception):
    """This client never holds a private key or wallet credential, for
    x402 any more than it does for L402. Carries the real accepts[0] terms
    back to the caller so THEY sign the exact-scheme USDC payment with
    their own wallet/CDP infra and retry with payment_signature set to
    the resulting proof -- mirroring PaymentRequired's L402 contract
    exactly (see that class's docstring). This client deliberately never
    constructs or sees the EIP-712 typed-data payload itself."""

    def __init__(
        self,
        *,
        resource_url: str,
        amount_atomic: str,
        asset: str,
        network: str,
        pay_to: str,
        extra_name: str,
        extra_version: str,
        max_timeout_seconds: int,
        x402_version: int,
    ):
        self.resource_url = resource_url
        self.amount_atomic = amount_atomic
        self.asset = asset
        self.network = network
        self.pay_to = pay_to
        self.extra_name = extra_name
        self.extra_version = extra_version
        self.max_timeout_seconds = max_timeout_seconds
        self.x402_version = x402_version
        super().__init__(
            f"payment required: sign an exact x402 payment of {amount_atomic} "
            f"atomic units of {asset} on {network} to {pay_to}, then retry "
            f"with payment_signature set to the resulting proof"
        )
