"""Increments 3 and 4 — Checkout, with and without reward redemption.

Increment 4 (the redemption path below) is the one to flag loudly to Tracks B,
C and D: it is ADR-001's logic going live, and C's runbook and D's governance
record both build on it.

The whole of checkout runs in a single transaction. The reason is ADR-001: the
balance check and the ledger append that spends against it must not be
separated by a commit, or the concurrency guarantee is gone regardless of what
the ADR says.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Customer, Order, OrderStatus
from app.schemas import CheckoutRequest, CheckoutResponse
from app.services import cart_client, rewards

router = APIRouter(tags=["checkout"])


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
def checkout(payload: CheckoutRequest, session: Session = Depends(get_session)):
    customer = session.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")

    # Contract 3.1 — consume the cart. Subtotal is taken from the Cart vertical
    # and never recomputed here; recomputing it would fork pricing across two
    # verticals and is exactly the seam the day-one contract exists to fix.
    try:
        cart = cart_client.get_cart(session, payload.cart_id)
    except cart_client.CartUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if cart.customer_id != payload.customer_id:
        raise HTTPException(status_code=403, detail="Cart belongs to another customer.")

    subtotal = cart.subtotal
    discount = 0.0
    points_redeemed = 0

    try:
        # --- Increment 4: redemption path -----------------------------------
        order = Order(
            customer_id=payload.customer_id,
            cart_id=payload.cart_id,
            subtotal=subtotal,
            discount_applied=0.0,
            total=subtotal,
            status=OrderStatus.CONFIRMED,
        )
        session.add(order)
        session.flush()  # assigns order.id without committing

        if payload.redeem_points > 0:
            max_useful = rewards.points_for_discount_cap(subtotal)
            if payload.redeem_points > max_useful:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Redemption of {payload.redeem_points} exceeds the order "
                        f"subtotal; at most {max_useful} points apply here."
                    ),
                )
            try:
                rewards.redeem_points(
                    session,
                    customer_id=payload.customer_id,
                    order_id=order.id,
                    points=payload.redeem_points,
                )
            except rewards.InsufficientBalance as exc:
                # R-R2. Rejected, not clamped: silently redeeming less than the
                # customer asked for is the failure mode Track C would have to
                # write a runbook for.
                raise HTTPException(status_code=409, detail=str(exc)) from exc

            points_redeemed = payload.redeem_points
            discount = rewards.discount_for_points(points_redeemed)

        order.discount_applied = discount
        order.total = round(subtotal - discount, 2)

        # --- Earn (policy: at placement; ADR-001 Section 4) ------------------
        # Earned on the pre-discount subtotal. Stated here because the
        # alternative — earning on the discounted total — is equally defensible
        # and the choice must not be inferred from the arithmetic.
        earn_entry = rewards.earn_points(
            session,
            customer_id=payload.customer_id,
            order_id=order.id,
            subtotal=subtotal,
        )
        points_earned = earn_entry.points if earn_entry is not None else 0

        balance_after = rewards.current_balance(session, payload.customer_id)
        if balance_after < 0:  # pragma: no cover — invariant guard
            raise RuntimeError(
                "Ledger invariant violated: balance negative after checkout."
            )

        session.commit()
    except Exception:
        session.rollback()
        raise

    return CheckoutResponse(
        order_id=order.id,
        subtotal=subtotal,
        discount_applied=discount,
        total=order.total,
        points_earned=points_earned,
        points_redeemed=points_redeemed,
        balance_after=balance_after,
        status=order.status.value,
    )


@router.post("/orders/{order_id}/cancel", status_code=200)
def cancel_order(order_id: str, session: Session = Depends(get_session)):
    """Cancellation. Note there is no bespoke reversal logic here — the whole
    handler delegates to one append operation, which is the practical payoff
    ADR-001 claims for Option C over A and B."""
    try:
        reversals = rewards.cancel_order(session, order_id=order_id)
        session.commit()
    except rewards.RewardError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

    return {
        "order_id": order_id,
        "status": OrderStatus.CANCELLED.value,
        "reversing_entries": len(reversals),
        "balance": rewards.current_balance(
            session, session.get(Order, order_id).customer_id
        ),
    }
