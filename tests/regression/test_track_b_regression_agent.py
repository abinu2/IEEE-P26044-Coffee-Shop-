"""Track B regression suite.

These tests are the gate for the main flows that should not break when Track A
ships a change. They test through the FastAPI surface where possible and keep
the database isolated from the local development database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app
from app.models import Base, Cart, CartItem, CartStatus, Order, RewardLedgerEntry


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False, "isolation_level": None},
        poolclass=StaticPool,
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
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield Session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_customer(client: TestClient, email: str = "trackb@example.com") -> dict:
    response = client.post("/customers", json={"email": email, "name": "Track B"})
    assert response.status_code == 201
    return response.json()


def add_cart(session_factory, *, customer_id: str, items: list[tuple[str, int, float]]) -> str:
    session = session_factory()
    try:
        cart = Cart(customer_id=customer_id, status=CartStatus.OPEN)
        session.add(cart)
        session.flush()
        for item, qty, unit_price in items:
            session.add(
                CartItem(
                    cart_id=cart.id,
                    item=item,
                    qty=qty,
                    unit_price=unit_price,
                )
            )
        session.commit()
        return cart.id
    finally:
        session.close()


def ledger_points(session_factory, customer_id: str) -> list[int]:
    session = session_factory()
    try:
        rows = (
            session.execute(
                select(RewardLedgerEntry)
                .where(RewardLedgerEntry.customer_id == customer_id)
                .order_by(RewardLedgerEntry.created_at, RewardLedgerEntry.id)
            )
            .scalars()
            .all()
        )
        return [row.points for row in rows]
    finally:
        session.close()


def order_count(session_factory) -> int:
    session = session_factory()
    try:
        return len(session.execute(select(Order)).scalars().all())
    finally:
        session.close()


def test_health_endpoint_stays_available(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_customer_profile_can_be_created_and_read_back(client):
    customer = create_customer(client, "customer-flow@example.com")

    response = client.get(f"/customers/{customer['id']}")

    assert response.status_code == 200
    assert response.json()["email"] == "customer-flow@example.com"


def test_duplicate_customer_email_is_rejected(client):
    create_customer(client, "duplicate@example.com")

    response = client.post(
        "/customers", json={"email": "duplicate@example.com", "name": "Duplicate"}
    )

    assert response.status_code == 409


def test_checkout_confirms_order_and_awards_rewards(client, session_factory):
    customer = create_customer(client, "checkout-award@example.com")
    cart_id = add_cart(
        session_factory,
        customer_id=customer["id"],
        items=[("latte", 2, 4.50), ("muffin", 1, 3.25)],
    )

    response = client.post(
        "/checkout",
        json={"cart_id": cart_id, "customer_id": customer["id"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == 12.25
    assert body["discount_applied"] == 0.0
    assert body["total"] == 12.25
    assert body["points_earned"] == 12
    assert body["points_redeemed"] == 0
    assert body["balance_after"] == 12
    assert body["status"] == "confirmed"
    assert ledger_points(session_factory, customer["id"]) == [12]


def test_checkout_redeems_points_and_keeps_balance_non_negative(
    client, session_factory
):
    customer = create_customer(client, "checkout-redeem@example.com")
    first_cart = add_cart(
        session_factory,
        customer_id=customer["id"],
        items=[("beans", 1, 150.00)],
    )
    first_response = client.post(
        "/checkout",
        json={"cart_id": first_cart, "customer_id": customer["id"]},
    )
    assert first_response.status_code == 201
    assert first_response.json()["balance_after"] == 150

    second_cart = add_cart(
        session_factory,
        customer_id=customer["id"],
        items=[("cold brew", 1, 5.00)],
    )
    response = client.post(
        "/checkout",
        json={
            "cart_id": second_cart,
            "customer_id": customer["id"],
            "redeem_points": 100,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == 5.0
    assert body["discount_applied"] == 1.0
    assert body["total"] == 4.0
    assert body["points_earned"] == 5
    assert body["points_redeemed"] == 100
    assert body["balance_after"] == 55
    points = ledger_points(session_factory, customer["id"])
    assert sorted(points) == [-100, 5, 150]
    assert sum(points) == 55


def test_checkout_rejects_redemption_above_available_balance(client, session_factory):
    customer = create_customer(client, "over-redeem@example.com")
    first_cart = add_cart(
        session_factory,
        customer_id=customer["id"],
        items=[("coffee", 1, 10.00)],
    )
    first_response = client.post(
        "/checkout",
        json={"cart_id": first_cart, "customer_id": customer["id"]},
    )
    assert first_response.status_code == 201
    assert first_response.json()["balance_after"] == 10

    second_cart = add_cart(
        session_factory,
        customer_id=customer["id"],
        items=[("espresso", 1, 5.00)],
    )
    before_orders = order_count(session_factory)

    response = client.post(
        "/checkout",
        json={
            "cart_id": second_cart,
            "customer_id": customer["id"],
            "redeem_points": 11,
        },
    )

    assert response.status_code == 409
    assert order_count(session_factory) == before_orders
    assert ledger_points(session_factory, customer["id"]) == [10]
    balance_response = client.get(f"/customers/{customer['id']}/balance")
    assert balance_response.status_code == 200
    assert balance_response.json()["balance"] == 10


def test_checkout_rejects_cart_owned_by_another_customer(client, session_factory):
    cart_owner = create_customer(client, "cart-owner@example.com")
    other_customer = create_customer(client, "cart-thief@example.com")
    cart_id = add_cart(
        session_factory,
        customer_id=cart_owner["id"],
        items=[("americano", 1, 4.00)],
    )

    response = client.post(
        "/checkout",
        json={"cart_id": cart_id, "customer_id": other_customer["id"]},
    )

    assert response.status_code == 403
    assert order_count(session_factory) == 0


def test_cancel_order_reverses_reward_entries(client, session_factory):
    customer = create_customer(client, "cancel-flow@example.com")
    cart_id = add_cart(
        session_factory,
        customer_id=customer["id"],
        items=[("pour over", 1, 20.00)],
    )
    checkout_response = client.post(
        "/checkout",
        json={"cart_id": cart_id, "customer_id": customer["id"]},
    )
    assert checkout_response.status_code == 201
    order_id = checkout_response.json()["order_id"]

    response = client.post(f"/orders/{order_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["balance"] == 0
    points = ledger_points(session_factory, customer["id"])
    assert sorted(points) == [-20, 20]
    assert sum(points) == 0


@pytest.mark.xfail(
    reason="Fulfillment scheduling is listed as Track A increment 5 but is not implemented yet.",
    strict=False,
)
def test_fulfillment_scheduling_contract_is_available_after_increment_5(client):
    response = client.post(
        "/fulfillment",
        json={
            "order_id": "example-order",
            "delivery_address": "100 Main St",
            "requested_window": "10:00-11:00",
        },
    )

    assert response.status_code == 201
    assert response.json()["state"] == "scheduled"
