"""Pydantic request/response models.

These types are the machine-readable form of the API contracts in
`docs/comms/day-one-contract.md`, Section 3. Track B tests against them and
Track C documents from them, so a change here is a contract change and triggers
the notification duty recorded in `docs/comms/increment-log.md`, Section 2.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- Profiles (increment 1) -------------------------------------------------


class CustomerCreate(BaseModel):
    email: EmailStr
    name: str | None = None


class CustomerOut(BaseModel):
    id: str
    email: str
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Rewards ----------------------------------------------------------------


class BalanceOut(BaseModel):
    """Derived, never stored (ADR-001). `as_of` exists so a caller can tell two
    reads apart; the balance is a computation, not a fact with a lifetime."""

    customer_id: str
    balance: int
    as_of: datetime


class LedgerEntryOut(BaseModel):
    id: str
    order_id: str | None
    type: str
    points: int
    reverses_entry_id: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Cart → Checkout (contract 3.1, consumed) -------------------------------


class CartItemView(BaseModel):
    item: str
    qty: int
    unit_price: float


class CartItemCreate(BaseModel):
    item: str = Field(min_length=1, max_length=255)
    qty: int = Field(gt=0)
    unit_price: float = Field(ge=0)


class CartCreate(BaseModel):
    customer_id: str
    items: list[CartItemCreate] = Field(min_length=1)


class CartView(BaseModel):
    """Shape Checkout expects from `GET /cart/{cart_id}`. Owned by the Cart
    vertical; reproduced here as the consumer's expectation."""

    cart_id: str
    customer_id: str
    items: list[CartItemView]
    subtotal: float


# --- Checkout (increments 3 and 4) ------------------------------------------


class CheckoutRequest(BaseModel):
    cart_id: str
    customer_id: str
    # Increment 3 ships with this absent/zero; increment 4 activates it. Partial
    # redemption is permitted — see requirements gap log, row 3.
    redeem_points: int = Field(default=0, ge=0)


class CheckoutResponse(BaseModel):
    order_id: str
    subtotal: float
    discount_applied: float
    total: float
    points_earned: int
    points_redeemed: int
    balance_after: int
    status: str


# --- Checkout → Fulfillment (contract 3.2, produced) ------------------------


class FulfillmentRequest(BaseModel):
    order_id: str
    delivery_address: str
    requested_window: str


class FulfillmentResponse(BaseModel):
    fulfillment_id: str
    state: str
    scheduled_window: str


class FulfillmentStateUpdate(BaseModel):
    state: str
