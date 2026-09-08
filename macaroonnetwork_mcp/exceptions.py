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
