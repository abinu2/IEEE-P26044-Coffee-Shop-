"""Fulfillment scheduling and controlled order-state transitions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Fulfillment, Order, OrderStatus
from app.schemas import FulfillmentRequest, FulfillmentResponse, FulfillmentStateUpdate

router = APIRouter(tags=["fulfillment"])

_TRANSITIONS = {
    OrderStatus.CONFIRMED: {OrderStatus.IN_PREPARATION, OrderStatus.CANCELLED},
    OrderStatus.IN_PREPARATION: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}


@router.post("/fulfillment", response_model=FulfillmentResponse, status_code=201)
def schedule(payload: FulfillmentRequest, session: Session = Depends(get_session)):
    order = session.get(Order, payload.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != OrderStatus.CONFIRMED:
        raise HTTPException(status_code=409, detail="Only confirmed orders can be scheduled.")
    existing = session.execute(
        select(Fulfillment).where(Fulfillment.order_id == payload.order_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Order is already scheduled.")

    fulfillment = Fulfillment(
        order_id=payload.order_id,
        state="scheduled",
        scheduled_window=payload.requested_window,
    )
    session.add(fulfillment)
    session.commit()
    return FulfillmentResponse(
        fulfillment_id=fulfillment.id,
        state=fulfillment.state,
        scheduled_window=fulfillment.scheduled_window,
    )


@router.patch("/fulfillment/{fulfillment_id}", response_model=FulfillmentResponse)
def update_state(
    fulfillment_id: str,
    payload: FulfillmentStateUpdate,
    session: Session = Depends(get_session),
):
    fulfillment = session.get(Fulfillment, fulfillment_id)
    if fulfillment is None:
        raise HTTPException(status_code=404, detail="Fulfillment not found.")
    order = session.get(Order, fulfillment.order_id)
    try:
        requested = OrderStatus(payload.state)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unknown fulfillment state.") from exc
    if requested not in _TRANSITIONS[order.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition order from {order.status.value} to {requested.value}.",
        )
    order.status = requested
    fulfillment.state = requested.value
    session.commit()
    return FulfillmentResponse(
        fulfillment_id=fulfillment.id,
        state=fulfillment.state,
        scheduled_window=fulfillment.scheduled_window,
    )
