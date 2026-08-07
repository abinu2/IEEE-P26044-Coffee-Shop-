"""Consumer side of contract 3.1 (Cart → Checkout).

STUB — owned by the Cart vertical, not by this one.

Everything Checkout knows about the cart passes through this module, so that
when the Cart owner's implementation lands, one function changes and no
checkout logic moves. The current implementation reads the shared tables
directly; if the contract later becomes an HTTP call between processes, replace
the body of `get_cart` and leave the signature alone.

If the shape returned here stops matching `CartView`, that is a day-one
contract breach, not a bug to work around locally.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cart, CartItem, CartStatus
from app.schemas import CartItemView, CartView


class CartUnavailable(Exception):
    """The cart could not be read, or is not in a checkout-eligible state."""


def get_cart(session: Session, cart_id: str) -> CartView:
    cart = session.get(Cart, cart_id)
    if cart is None:
        raise CartUnavailable(f"Cart {cart_id} not found.")
    if cart.status != CartStatus.OPEN:
        raise CartUnavailable(f"Cart {cart_id} is {cart.status.value}, not open.")

    rows = list(
        session.execute(select(CartItem).where(CartItem.cart_id == cart_id))
        .scalars()
        .all()
    )
    if not rows:
        raise CartUnavailable(f"Cart {cart_id} is empty.")

    items = [
        CartItemView(item=r.item, qty=r.qty, unit_price=r.unit_price) for r in rows
    ]
    subtotal = round(sum(r.qty * r.unit_price for r in rows), 2)

    return CartView(
        cart_id=cart.id,
        customer_id=cart.customer_id,
        items=items,
        subtotal=subtotal,
    )


def mark_checked_out(session: Session, cart_id: str) -> None:
    """Consume an open cart in the caller's checkout transaction."""
    cart = session.get(Cart, cart_id)
    if cart is None or cart.status != CartStatus.OPEN:
        raise CartUnavailable(f"Cart {cart_id} is not open.")
    cart.status = CartStatus.CHECKED_OUT
