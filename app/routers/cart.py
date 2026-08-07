"""Cart endpoints owned by the Cart/Fulfillment Track A vertical."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Cart, CartItem, Customer
from app.schemas import CartCreate, CartView
from app.services import cart_client

router = APIRouter(tags=["cart"])


@router.post("/cart", response_model=CartView, status_code=201)
def create_cart(payload: CartCreate, session: Session = Depends(get_session)):
    if session.get(Customer, payload.customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found.")

    cart = Cart(customer_id=payload.customer_id)
    session.add(cart)
    session.flush()
    for item in payload.items:
        session.add(CartItem(cart_id=cart.id, **item.model_dump()))
    session.commit()
    return cart_client.get_cart(session, cart.id)


@router.get("/cart/{cart_id}", response_model=CartView)
def read_cart(cart_id: str, session: Session = Depends(get_session)):
    try:
        return cart_client.get_cart(session, cart_id)
    except cart_client.CartUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
