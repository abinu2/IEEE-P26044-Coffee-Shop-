"""Producer side of contract 3.2 (Checkout → Fulfillment).

STUB — the endpoint is owned by the Fulfillment vertical.

Per the day-one contract, Section 3.2, Fulfillment does not re-validate payment
or rewards; Checkout guarantees that any order handed over is confirmed, paid
and valid. That guarantee is why this call is made after the checkout
transaction commits and not inside it: handing an order to Fulfillment that a
later rollback erases would break the contract in the one direction the
contract does not defend against.

Increment 5 wires this up. Until then it raises, so that a premature call fails
loudly rather than silently succeeding against a stub.
"""

from __future__ import annotations

from app.schemas import FulfillmentRequest, FulfillmentResponse


class FulfillmentUnavailable(Exception):
    pass


def schedule(request: FulfillmentRequest) -> FulfillmentResponse:
    raise FulfillmentUnavailable(
        "Fulfillment vertical not yet delivered (increment 5). "
        "See docs/comms/day-one-contract.md, Section 3.2."
    )
