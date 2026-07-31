"""Reward ledger service — the implementation of ADR-001, Option C.

Every rule the ADR commits to lives in this one module. Nothing outside it
should write to `reward_ledger`, because the correctness properties the ADR
claims (balance never negative; cancellation handled uniformly; no lost update
under concurrent redemption) are properties of these functions, not of the
schema alone.

The invariant handed to Track B, stated once:

    For every customer, at every observable moment,
        balance == SUM(reward_ledger.points WHERE customer_id = c)
    and balance >= 0.

There is no second definition of balance anywhere in the codebase to disagree
with this one. That is the whole point of the decision.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    LedgerEntryType,
    Order,
    OrderStatus,
    RewardLedgerEntry,
)

# --- Earn policy ------------------------------------------------------------
# Recorded as a requirement, not an architecture decision: ADR-001 Section 4
# notes explicitly that the placement-vs-fulfillment question does not affect
# the storage model. Earn-at-placement keeps this vertical independent of the
# Fulfillment slice; cancellation is absorbed by a reversing entry.
POINTS_PER_CURRENCY_UNIT = 1  # 1 point per whole dollar of subtotal
CURRENCY_PER_POINT = 0.01  # 100 points = $1.00 discount


class RewardError(Exception):
    """Base class for reward-domain failures."""


class InsufficientBalance(RewardError):
    """Raised when a redemption would drive the balance below zero.

    This exception existing is not a defensive nicety — R-R2 requires the
    rejection, and Track C's reward-miscalculation runbook keys off it.
    """


def points_for_subtotal(subtotal: float) -> int:
    """Points earned by an order of the given subtotal.

    Floor rather than round: awarding points for money not spent is the error
    direction that compounds silently across a ledger.
    """
    return int(subtotal * POINTS_PER_CURRENCY_UNIT)


def discount_for_points(points: int) -> float:
    """Currency discount obtained by redeeming `points`."""
    return round(points * CURRENCY_PER_POINT, 2)


def points_for_discount_cap(subtotal: float) -> int:
    """Most points that can usefully be applied to an order of this subtotal.

    A discount may not exceed the order value — enforced in the schema by
    `ck_order_discount_within_subtotal`, and rejected up front here so the
    customer gets a 422 explaining the cap rather than a constraint error.
    """
    return int(subtotal / CURRENCY_PER_POINT)


def current_balance(session: Session, customer_id: str) -> int:
    """The authoritative balance. A computation, never a stored column."""
    total = session.execute(
        select(func.coalesce(func.sum(RewardLedgerEntry.points), 0)).where(
            RewardLedgerEntry.customer_id == customer_id
        )
    ).scalar_one()
    return int(total)


def ledger_for_customer(
    session: Session, customer_id: str
) -> list[RewardLedgerEntry]:
    """Full history, oldest first. This is Track C's audit trail."""
    return list(
        session.execute(
            select(RewardLedgerEntry)
            .where(RewardLedgerEntry.customer_id == customer_id)
            .order_by(RewardLedgerEntry.created_at, RewardLedgerEntry.id)
        )
        .scalars()
        .all()
    )


def lock_customer_for_redemption(session: Session, customer_id: str) -> None:
    """Serialize the read-then-append sequence that spends a balance.

    Read-then-append is not atomic on its own: two concurrent redemptions can
    each read a balance of 100, each append -100, and leave the customer at
    -100 (ADR-001, Section 1, force 2).

    On SQLite this is already handled at the engine level — every transaction
    begins with BEGIN IMMEDIATE (see app/db.py), so writers serialize and the
    window does not exist. This function is therefore a no-op there, and exists
    so that the locking requirement is stated at the point it applies rather
    than being discoverable only in engine configuration.

    On a row-locking dialect it takes an explicit lock on the customer row.

    Called only on the redemption path. Earning does not need it: appending a
    positive entry cannot violate the non-negative invariant under any
    interleaving.
    """
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect in {"postgresql", "mysql"}:
        session.execute(
            select(Customer.id).where(Customer.id == customer_id).with_for_update()
        )
    # sqlite: covered by BEGIN IMMEDIATE in app/db.py


def earn_points(
    session: Session,
    *,
    customer_id: str,
    order_id: str,
    subtotal: float,
    reason: str | None = None,
) -> RewardLedgerEntry | None:
    """Append the earn entry for a confirmed order.

    Returns None when the order earns zero points (a sub-unit order), because
    the ledger rejects zero-point rows: an entry that changes nothing is noise
    in an audit trail. Callers must not treat None as failure.
    """
    points = points_for_subtotal(subtotal)
    if points == 0:
        return None

    entry = RewardLedgerEntry(
        customer_id=customer_id,
        order_id=order_id,
        type=LedgerEntryType.EARN,
        points=points,
        reason=reason or "order placed",
    )
    session.add(entry)
    session.flush()
    return entry


def redeem_points(
    session: Session,
    *,
    customer_id: str,
    order_id: str,
    points: int,
    reason: str | None = None,
) -> RewardLedgerEntry:
    """Append a redemption, rejecting it if the balance cannot cover it.

    The balance check and the append occur inside one transaction held by the
    caller. Do not commit between them.
    """
    if points <= 0:
        raise RewardError("Redemption must be a positive number of points.")

    lock_customer_for_redemption(session, customer_id)

    available = current_balance(session, customer_id)
    if points > available:
        raise InsufficientBalance(
            f"Redemption of {points} exceeds available balance of {available}."
        )

    entry = RewardLedgerEntry(
        customer_id=customer_id,
        order_id=order_id,
        type=LedgerEntryType.REDEEM,
        points=-points,
        reason=reason or "checkout redemption",
    )
    session.add(entry)
    session.flush()
    return entry


def reverse_entries_for_order(
    session: Session, *, order_id: str, reason: str
) -> list[RewardLedgerEntry]:
    """Reverse every unreversed ledger entry attached to an order.

    This single function is the entire cancellation and refund path. There is no
    separate reversal logic to keep in step with the earn path, which was the
    argument against Options A and B: a reversal here is the same append
    operation as everything else, with the sign flipped.

    Reversing a redemption returns the points (positive entry); reversing an
    earn removes them (negative entry). The latter can drive a balance negative
    if the customer has already spent points earned against an order that was
    subsequently cancelled. That is a real domain question, not a bug in the
    ledger, and it is flagged below rather than silently resolved.
    """
    entries = list(
        session.execute(
            select(RewardLedgerEntry).where(RewardLedgerEntry.order_id == order_id)
        )
        .scalars()
        .all()
    )
    already_reversed = {
        e.reverses_entry_id for e in entries if e.reverses_entry_id is not None
    }

    reversals: list[RewardLedgerEntry] = []
    for entry in entries:
        if entry.type == LedgerEntryType.REVERSE or entry.id in already_reversed:
            continue
        reversal = RewardLedgerEntry(
            customer_id=entry.customer_id,
            order_id=order_id,
            type=LedgerEntryType.REVERSE,
            points=-entry.points,
            reverses_entry_id=entry.id,
            reason=reason,
        )
        session.add(reversal)
        reversals.append(reversal)

    session.flush()
    return reversals


def cancel_order(
    session: Session, *, order_id: str, reason: str = "order cancelled"
) -> list[RewardLedgerEntry]:
    """Mark an order cancelled and reverse its reward effects."""
    order = session.get(Order, order_id)
    if order is None:
        raise RewardError(f"Unknown order {order_id}.")
    order.status = OrderStatus.CANCELLED
    return reverse_entries_for_order(session, order_id=order_id, reason=reason)


def balance_as_of_now(session: Session, customer_id: str) -> tuple[int, datetime]:
    return current_balance(session, customer_id), datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# OPEN DOMAIN QUESTION — resolve with the requirements, not in code
#
# If a customer earns 100 points on order X, spends them on order Y, and order X
# is then cancelled, the reversal of X's earn leaves the balance at -100. The
# ledger is arithmetically correct; the policy is undecided. Options: allow the
# transient negative and block further redemption until it clears; reverse only
# down to zero and absorb the loss; or claw back the discount on Y.
#
# This is deliberately left open and visible. It is the same class of omission
# ADR-001 Section 5 records the tool making — a correctness question that a
# structurally complete design does not force you to notice. Record the
# resolution in the requirements spec (R-R2 or a new R-R4) before increment 4
# ships, and log in the gap table whether the AI surfaced it unprompted.
# ---------------------------------------------------------------------------
