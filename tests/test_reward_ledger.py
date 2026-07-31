"""Tests for the ADR-001 invariant.

These are the executable form of what ADR-001, Section 4 hands to Track B:

    balance == SUM(reward_ledger.points)  and  balance >= 0

Track B's regression agent should treat this file as the starting point for the
rewards flow rather than generating its own from the endpoint surface — the
invariant is a property of the ledger, and testing it only through HTTP would
miss the cases below.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models import Base, Cart, CartItem, Customer, LedgerEntryType, Order
from app.services import rewards


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False, "isolation_level": None}
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def customer(session):
    c = Customer(email="allan@example.com", name="Allan")
    session.add(c)
    session.commit()
    return c


def _order(session, customer, subtotal=10.0):
    o = Order(
        customer_id=customer.id,
        cart_id="cart-1",
        subtotal=subtotal,
        discount_applied=0.0,
        total=subtotal,
    )
    session.add(o)
    session.flush()
    return o


# --- The invariant ----------------------------------------------------------


def test_balance_equals_signed_ledger_sum(session, customer):
    o = _order(session, customer, 25.0)
    rewards.earn_points(
        session, customer_id=customer.id, order_id=o.id, subtotal=25.0
    )
    session.commit()

    entries = rewards.ledger_for_customer(session, customer.id)
    assert rewards.current_balance(session, customer.id) == sum(
        e.points for e in entries
    )


def test_redemption_cannot_drive_balance_negative(session, customer):
    o = _order(session, customer, 10.0)
    rewards.earn_points(session, customer_id=customer.id, order_id=o.id, subtotal=10.0)
    session.commit()
    assert rewards.current_balance(session, customer.id) == 10

    o2 = _order(session, customer, 5.0)
    with pytest.raises(rewards.InsufficientBalance):
        rewards.redeem_points(
            session, customer_id=customer.id, order_id=o2.id, points=11
        )
    session.rollback()

    assert rewards.current_balance(session, customer.id) == 10


def test_exact_balance_redemption_is_allowed(session, customer):
    o = _order(session, customer, 10.0)
    rewards.earn_points(session, customer_id=customer.id, order_id=o.id, subtotal=10.0)
    session.commit()

    o2 = _order(session, customer, 5.0)
    rewards.redeem_points(session, customer_id=customer.id, order_id=o2.id, points=10)
    session.commit()

    assert rewards.current_balance(session, customer.id) == 0


# --- Reversal (the Option C payoff) -----------------------------------------


def test_cancellation_reverses_earned_points(session, customer):
    o = _order(session, customer, 30.0)
    rewards.earn_points(session, customer_id=customer.id, order_id=o.id, subtotal=30.0)
    session.commit()
    assert rewards.current_balance(session, customer.id) == 30

    rewards.cancel_order(session, order_id=o.id)
    session.commit()

    assert rewards.current_balance(session, customer.id) == 0
    types = [e.type for e in rewards.ledger_for_customer(session, customer.id)]
    assert types == [LedgerEntryType.EARN, LedgerEntryType.REVERSE]


def test_cancellation_returns_redeemed_points(session, customer):
    o1 = _order(session, customer, 50.0)
    rewards.earn_points(session, customer_id=customer.id, order_id=o1.id, subtotal=50.0)
    session.commit()

    o2 = _order(session, customer, 5.0)
    rewards.redeem_points(session, customer_id=customer.id, order_id=o2.id, points=20)
    session.commit()
    assert rewards.current_balance(session, customer.id) == 30

    rewards.cancel_order(session, order_id=o2.id)
    session.commit()

    # The redemption is returned; o2 earned nothing yet in this fixture, so the
    # balance goes back to 50.
    assert rewards.current_balance(session, customer.id) == 50


def test_reversal_is_idempotent(session, customer):
    """Cancelling twice must not double-reverse. The DB constraint enforces it,
    but the service must not rely on catching the error."""
    o = _order(session, customer, 20.0)
    rewards.earn_points(session, customer_id=customer.id, order_id=o.id, subtotal=20.0)
    session.commit()

    rewards.cancel_order(session, order_id=o.id)
    session.commit()
    second = rewards.cancel_order(session, order_id=o.id)
    session.commit()

    assert second == []
    assert rewards.current_balance(session, customer.id) == 0


# --- Arithmetic -------------------------------------------------------------


def test_points_floor_rather_than_round(session):
    assert rewards.points_for_subtotal(4.99) == 4
    assert rewards.points_for_subtotal(5.00) == 5
    assert rewards.points_for_subtotal(0.50) == 0


def test_zero_point_order_writes_no_entry(session, customer):
    o = _order(session, customer, 0.50)
    entry = rewards.earn_points(
        session, customer_id=customer.id, order_id=o.id, subtotal=0.50
    )
    session.commit()
    assert entry is None
    assert rewards.ledger_for_customer(session, customer.id) == []


def test_discount_conversion():
    assert rewards.discount_for_points(100) == 1.00
    assert rewards.discount_for_points(250) == 2.50


# --- Known-open policy question ---------------------------------------------


@pytest.mark.xfail(
    reason=(
        "Open domain question, deliberately unresolved: reversing an earn after "
        "those points were spent can leave a negative balance. See the note at "
        "the foot of app/services/rewards.py. Resolve in the requirements spec "
        "before increment 4 ships, then replace this xfail with the decided "
        "behaviour."
    ),
    strict=False,
)
def test_balance_never_negative_after_earn_reversal(session, customer):
    o1 = _order(session, customer, 100.0)
    rewards.earn_points(
        session, customer_id=customer.id, order_id=o1.id, subtotal=100.0
    )
    session.commit()

    o2 = _order(session, customer, 5.0)
    rewards.redeem_points(session, customer_id=customer.id, order_id=o2.id, points=100)
    session.commit()

    rewards.cancel_order(session, order_id=o1.id)
    session.commit()

    assert rewards.current_balance(session, customer.id) >= 0
