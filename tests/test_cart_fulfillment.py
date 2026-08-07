"""Track A Cart/Fulfillment vertical tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app
from app.models import Base, Cart, CartStatus


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False, "isolation_level": None}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override():
        with session_factory() as session:
            yield session
    app.dependency_overrides[get_session] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _customer(client):
    return client.post("/customers", json={"email": "cart-owner@example.com", "name": "Cart Owner"}).json()


def test_cart_is_created_and_priced(client):
    customer = _customer(client)
    response = client.post("/cart", json={"customer_id": customer["id"], "items": [
        {"item": "latte", "qty": 2, "unit_price": 4.5},
        {"item": "muffin", "qty": 1, "unit_price": 3.25},
    ]})
    assert response.status_code == 201
    assert response.json()["subtotal"] == 12.25
    assert client.get(f"/cart/{response.json()['cart_id']}").json() == response.json()


def test_checkout_consumes_cart_and_prevents_second_order(client, session_factory):
    customer = _customer(client)
    cart_id = client.post("/cart", json={"customer_id": customer["id"], "items": [
        {"item": "espresso", "qty": 1, "unit_price": 3.0}
    ]}).json()["cart_id"]
    payload = {"cart_id": cart_id, "customer_id": customer["id"]}
    assert client.post("/checkout", json=payload).status_code == 201
    assert client.post("/checkout", json=payload).status_code == 502
    with session_factory() as session:
        assert session.get(Cart, cart_id).status == CartStatus.CHECKED_OUT


def test_fulfillment_schedules_and_advances_valid_states(client):
    customer = _customer(client)
    cart = client.post("/cart", json={"customer_id": customer["id"], "items": [
        {"item": "beans", "qty": 1, "unit_price": 15.0}
    ]}).json()
    order = client.post("/checkout", json={"cart_id": cart["cart_id"], "customer_id": customer["id"]}).json()
    scheduled = client.post("/fulfillment", json={"order_id": order["order_id"], "delivery_address": "100 Main St", "requested_window": "10:00-11:00"})
    assert scheduled.status_code == 201
    fid = scheduled.json()["fulfillment_id"]
    assert client.patch(f"/fulfillment/{fid}", json={"state": "in_preparation"}).status_code == 200
    assert client.patch(f"/fulfillment/{fid}", json={"state": "completed"}).json()["state"] == "completed"
    assert client.patch(f"/fulfillment/{fid}", json={"state": "in_preparation"}).status_code == 409


def test_fulfillment_rejects_duplicate_schedule(client):
    customer = _customer(client)
    cart = client.post("/cart", json={"customer_id": customer["id"], "items": [
        {"item": "tea", "qty": 1, "unit_price": 4.0}
    ]}).json()
    order_id = client.post("/checkout", json={"cart_id": cart["cart_id"], "customer_id": customer["id"]}).json()["order_id"]
    payload = {"order_id": order_id, "delivery_address": "100 Main St", "requested_window": "10:00-11:00"}
    assert client.post("/fulfillment", json=payload).status_code == 201
    assert client.post("/fulfillment", json=payload).status_code == 409
