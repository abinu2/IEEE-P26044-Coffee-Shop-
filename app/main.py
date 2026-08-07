"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload
Interactive contract browser:  http://127.0.0.1:8000/docs

The OpenAPI document generated at /openapi.json is the machine-readable form of
the API contracts. Track B tests against it; Track C documents from it. Treat a
diff in that document as a coordination event under
`docs/comms/increment-log.md`, Section 2.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.db import init_db
from app.routers import cart, checkout, customers, fulfillment

app = FastAPI(
    title="Coffee Shop — IEEE P26044 Reference Project",
    description=(
        "Track A (Build): profiles and rewards; cart, checkout, and fulfillment. "
        "Reward points follow ADR-001 (immutable ledger, derived balance)."
    ),
    version="0.1.0",
)

app.include_router(customers.router)
app.include_router(checkout.router)
app.include_router(cart.router)
app.include_router(fulfillment.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
