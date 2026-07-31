"""Increment 1 — Customer profiles.  Notice due to Track B on delivery."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Customer
from app.schemas import BalanceOut, CustomerCreate, CustomerOut, LedgerEntryOut
from app.services import rewards

router = APIRouter(tags=["customers"])


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, session: Session = Depends(get_session)):
    existing = session.execute(
        select(Customer).where(Customer.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered."
        )

    customer = Customer(email=payload.email, name=payload.name)
    session.add(customer)
    session.commit()
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, session: Session = Depends(get_session)):
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return customer


@router.get("/customers/{customer_id}/balance", response_model=BalanceOut)
def get_balance(customer_id: str, session: Session = Depends(get_session)):
    """Derived on every read (ADR-001). No cached value is consulted."""
    if session.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    balance, as_of = rewards.balance_as_of_now(session, customer_id)
    return BalanceOut(customer_id=customer_id, balance=balance, as_of=as_of)


@router.get(
    "/customers/{customer_id}/ledger", response_model=list[LedgerEntryOut]
)
def get_ledger(customer_id: str, session: Session = Depends(get_session)):
    """Full reward history. Exists for Track C's audit trail as much as for the
    customer — a miscalculation incident is diagnosed from this endpoint."""
    if session.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return rewards.ledger_for_customer(session, customer_id)
