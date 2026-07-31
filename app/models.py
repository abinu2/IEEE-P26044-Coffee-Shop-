"""
SQLAlchemy schema — Coffee Shop Reference Project.

This module is the physical realization of the shared schema fixed in
`docs/comms/day-one-contract.md`, Section 2. Both Track A feature verticals read
from it; ownership of each table is annotated below and enforced by convention
rather than by the database.

The rewards model implements ADR-001, Option C: there is no stored balance
column anywhere in this schema. The authoritative balance is the signed sum of
`reward_ledger` rows for a customer. Adding a `balance` column to `customers`
would reintroduce the mutable source of truth the ADR exists to exclude; if a
materialized sum is ever added for read performance, it must live in a table
named as a cache and be reconstructible from the ledger alone.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class LedgerEntryType(str, enum.Enum):
    """Fixed by ADR-001, Section 4. Do not extend without a superseding ADR."""

    EARN = "earn"
    REDEEM = "redeem"
    REVERSE = "reverse"


class OrderStatus(str, enum.Enum):
    """`confirmed` is written by Checkout. Every later value is written by the
    Fulfillment vertical (day-one contract, Section 2)."""

    CONFIRMED = "confirmed"
    IN_PREPARATION = "in_preparation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CartStatus(str, enum.Enum):
    OPEN = "open"
    CHECKED_OUT = "checked_out"
    ABANDONED = "abandoned"


# ---------------------------------------------------------------------------
# Profiles / Rewards vertical  (owner: Allan)
# ---------------------------------------------------------------------------


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    ledger_entries: Mapped[list["RewardLedgerEntry"]] = relationship(
        back_populates="customer"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    # NOTE (ADR-001): no `points_balance` column. Balance is derived. See
    # app/services/rewards.py::current_balance.


class RewardLedgerEntry(Base):
    """Append-only. Rows are never updated or deleted.

    Sign convention — `points` is stored as a signed integer so that the balance
    is a plain SUM with no type-dependent branching:

        earn     → positive
        redeem   → negative
        reverse  → negation of the entry it reverses (usually negative, but
                   negative-earn reversal is positive when a redemption itself
                   is reversed)

    The CHECK constraints below encode that convention at the storage layer, so
    a mis-signed row cannot be written even by code that bypasses the service.
    """

    __tablename__ = "reward_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), index=True)
    type: Mapped[LedgerEntryType] = mapped_column(
        Enum(LedgerEntryType, native_enum=False), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    # Set on a `reverse` entry to identify the entry being reversed. Gives
    # Track C an unambiguous audit chain for a miscalculation incident.
    reverses_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("reward_ledger.id")
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    customer: Mapped["Customer"] = relationship(back_populates="ledger_entries")

    __table_args__ = (
        CheckConstraint("points != 0", name="ck_ledger_points_nonzero"),
        CheckConstraint(
            "(type != 'earn') OR (points > 0)", name="ck_ledger_earn_positive"
        ),
        CheckConstraint(
            "(type != 'redeem') OR (points < 0)", name="ck_ledger_redeem_negative"
        ),
        CheckConstraint(
            "(type != 'reverse') OR (reverses_entry_id IS NOT NULL)",
            name="ck_ledger_reverse_has_target",
        ),
        # An order may be earned against at most once. Prevents a retried
        # checkout from double-awarding; the reversal path is unaffected
        # because reversals carry type='reverse'.
        Index(
            "uq_ledger_one_earn_per_order",
            "order_id",
            unique=True,
            sqlite_where=type == LedgerEntryType.EARN,
        ),
        # Each entry may be reversed at most once.
        UniqueConstraint("reverses_entry_id", name="uq_ledger_single_reversal"),
    )


# ---------------------------------------------------------------------------
# Shared  (created by Checkout; `status` updated by Fulfillment)
# ---------------------------------------------------------------------------


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    cart_id: Mapped[str] = mapped_column(String(36), nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    discount_applied: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False),
        nullable=False,
        default=OrderStatus.CONFIRMED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    customer: Mapped["Customer"] = relationship(back_populates="orders")

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_order_subtotal_nonneg"),
        CheckConstraint("discount_applied >= 0", name="ck_order_discount_nonneg"),
        CheckConstraint("total >= 0", name="ck_order_total_nonneg"),
        CheckConstraint(
            "discount_applied <= subtotal", name="ck_order_discount_within_subtotal"
        ),
    )


# ---------------------------------------------------------------------------
# Cart / Fulfillment vertical  (owner: teammate)
#
# Declared here only so that a single Base creates a coherent database during
# local development and so foreign keys resolve. The Cart/Fulfillment owner is
# free to replace these definitions; the fields named in the day-one contract,
# Section 2 are the part this vertical relies on and must not change without
# a contract amendment.
# ---------------------------------------------------------------------------


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    status: Mapped[CartStatus] = mapped_column(
        Enum(CartStatus, native_enum=False), nullable=False, default=CartStatus.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart")


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), nullable=False)
    item: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")

    __table_args__ = (CheckConstraint("qty > 0", name="ck_cart_item_qty_positive"),)


class Fulfillment(Base):
    __tablename__ = "fulfillments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_window: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
